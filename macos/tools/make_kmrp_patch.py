#!/usr/bin/env python3
"""Build KMRP for macOS as one KotOR Patch Manager patch, `kmrp`.

The patch is FTD's two patches, built from their source as KPM's Patches/create-patch.py builds
them, with KMRP's own code linked into the same module:

    K1WidescreenPatch   FTD and RaymanGT (MIT): the resolution, and with
                        UseGuiFileLayouts=1 no layout of its own
    K1StrayBugFixes     RaymanGT, FTD (MIT): the engine fixes that hold at any resolution
    kmrp-layout         KMRP: the sizes, lists, popups and map of KMRP's menu layouts
    kmrp-map-notes      KMRP: Derslok's map-note corrections (optional)
    kmrp-controller     KMRP: controller support (optional)
    kmrp-assets         KMRP: every resolution's menu set and the artwork, inside the module
                        (--assets, with the bank macos/tools/make_kmrp_assets.py packs)

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
        [--no-map-notes] [--no-controller] [--options]
        [--assets DIR --assets-bank FILE --tools DIR] --out FILE.kpatch

--options builds the whole patch once, with the optional parts as patch options of a KotOR
Patch Manager that has them (LaneDibello/Kotor-Patch-Manager#310: `[[patch.options]]` in the
manifest, `when` on a hook), instead of leaving them out of the build. They are Windows' three
(tools/build_native_kpatch.py, OPTIONS), and as there only the controller's hooks depend on one:

    controller   its hooks carry `when = "controller"`; what its code installs on its own asks
                 kmrp-layout/options.cpp
    map-notes    its hook stays, and its handler asks the option
    debug-logs   no hook: the module's diagnostic log is written only while it is on

Whoever installs records the choice in configs/kmrp.ini beside the game, which the module reads
(kmrp-layout/options.cpp). A manager without options ignores both keys, installs every hook and
writes no file, which the module reads as the defaults: the patch built with neither --no flag,
and no log. So the same file installs on either. For that to hold no two hooks may share an
address, which such a manager refuses: the GUI frame hook the controller shares with the build
without it (SHARED_HOOKS) stays unconditional and chooses in its handler.

--assets DIR --assets-bank FILE --tools DIR makes the patch whole without KMRP Installer: the bank
of menu sets and artwork is linked into the module as the section __KMRP,__assets, with the part
that unpacks and registers it (patches/kmrp-assets) and the installer's three helpers compiled in
(tools/kmrp-guiblend.c, kmrp-abilityicons.c, kmrp-gameart.c). That part is linked first: its
constructor has to run before the widescreen patch's, which reads swkotor.ini, and the
widescreen patch is compiled with -Dfopen=kmrp_ini_fopen so that read asks the part
(kmrp-assets/layouts_ini.cpp).

--without-option ID (with --options) writes, instead of the patch, what an installer that
resolved the options installs with that option off: the same module, the hook list without that
option's hooks and without conditions, and no options in the manifest. KMRP's installer is such
an installer, and KPM's KPatchCore stages its hook list from this file (macos/build.sh); it is
not shipped.
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
# The installer's helpers as the module compiles them in (their embedded entry points).
HELPERS = [("kmrp-guiblend.c", "-DKMRP_GUI_EMBEDDED"), ("kmrp-abilityicons.c", "-DKMRP_EMBEDDED"),
           ("kmrp-gameart.c", "-DKMRP_EMBEDDED")]
HELPER_FLAGS = ["-arch", "x86_64", "-std=c11", "-O2", "-mmacosx-version-min=10.9", "-w"]
LINK_FLAGS = ["-arch", "x86_64", "-dynamiclib", "-mmacosx-version-min=10.13", "-framework", "OpenGL",
              "-Wl,-dead_strip_dylibs", "-install_name", "@executable_path/macos_x86_64.dylib"]
CONTROLLER_LINK = ["-fobjc-arc", "-fobjc-link-runtime", "-framework", "Foundation", "-framework", "AppKit",
                   "-framework", "ApplicationServices", "-weak_framework", "GameController"]


# KMRP's options (--options), in the order the launcher lists them: Windows' (tools/
# build_native_kpatch.py, OPTIONS). Map notes default to on: a manager without options installs
# every hook, and the default has to be what it installs. Controller support was the first of
# them until 2026-10-07; it is a patch of its own now (--controller-patch).
OPTIONS = [
    ("map-notes", "Map notes", True,
     "Shows the area map's notes where they belong (Derslok's map marker corrections)."),
    # Since 2026-10-08 (the maintainer, after a player asked whether the bundled mods have to be
    # installed): the icon pack is in the module either way, and the module leaves its files out
    # of what it gives the game when this is off (kmrp-assets/assets.cpp, LinkArtwork).
    ("hd-icons", "HD icons", True,
     "Uses JackInTheBox's HD Icon Pack for the item icons. Off: the game's own item icons."),
    ("debug-logs", "Debug logs", False,
     "Writes a diagnostic log file. Leave off unless you are reporting a problem."),
]
# The controller patch's (tools/build_controller_kpatch.py, OPTIONS).
CONTROLLER_OPTIONS = [
    # On by default on the Mac (the maintainer, 2026-10-07: "this is standard with controller"); off
    # by default on Windows.
    ("xbox-hud", "Xbox-style HUD", True,
     "Lays the in-game HUD out like the original Xbox version's while the pad is in use: the action slots in a "
     "box at the bottom left, the target's name at the top left, the party at the bottom right. Without a "
     "manager that offers options, set Style=PC under [Hud] in kmrp-controller.ini to keep the game's own HUD."),
    ("debug-logs", "Debug logs", False,
     "Writes diagnostic log files. Leave off unless you are reporting a problem."),
]
CONTROLLER_ID = "kmrp-controller"
# "(macOS)": the Windows patch of this id has the name without it, and neither runs on the
# other system (the maintainer, 2026-10-08: the Mac's patch files say what they are for).
CONTROLLER_NAME = "KOTOR 1 Native Controller Mod + Xbox HUD (macOS)"
CONTROLLER_DESCRIPTION = (
    "Native controller support for KOTOR: play with an Xbox, PlayStation, Switch or Steam Deck "
    "controller in the game and in every menu, with matching button prompts, rumble and a Controller "
    "Layout screen in Options. Needs no other patch and writes nothing to the game's override folder. "
    "KMRP installs it as its controller support; it works the same on the game without KMRP.")
# Other authors' patches that hook this patch's sites on Windows (tools/check_kpm_overlaps.py);
# listed here as there, though neither has a macOS build.
CONTROLLER_CONFLICTS = ["expanded-keyboard-control", "xbox-controls-k1"]
# The parts whose hooks are installed only while an option is on: none. The map notes' one hook
# stays, and its handler asks the option (kmrp-map-notes/map_notes.cpp).
PART_OPTION: dict[str, str] = {}
SHARED_HOOKS: set[int] = set()


def fail(message: str) -> None:
    raise SystemExit(f"make_kmrp_patch: {message}")


def sources(directory: Path, patterns: tuple[str, ...]) -> list[Path]:
    """create-patch.py's find_sources: the folder and one level below, sorted."""
    return sorted(p for pattern in patterns for p in (*directory.glob(pattern), *directory.glob(f"*/{pattern}")))


def compile_part(files: list[Path], flags: list[str], objects: Path, tag: str) -> list[Path]:
    out = []
    for source in files:
        obj = objects / f"{tag}-{source.parent.name}-{source.stem}.o"
        compiler = "clang" if source.suffix == ".c" else "clang++"
        result = subprocess.run([compiler, *flags, "-c", str(source), "-o", str(obj)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"{source}: does not compile\n{result.stderr}")
        out.append(obj)
    return out


# ---------------------------------------------------------------------------------- hooks
class Hook:
    def __init__(self, part: str, prefix: list[str], body: list[str], when: str | None = None):
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
        # The option the hook is installed with, written after the hook's own keys, before its
        # first parameter table.
        self.when = when if when and self.address not in SHARED_HOOKS else None
        self.keys = len(head)

    def text(self, conditions: bool = True) -> str:
        body = self.body
        if conditions and self.when:
            body = [*body[:self.keys], f'when = "{self.when}"', *body[self.keys:]]
        return "\n".join([*self.prefix, "[[hooks]]", *body]).rstrip() + "\n"


def read_hooks(part: str, path: Path, when: str | None = None) -> list[Hook]:
    lines = path.read_text().splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == "[[hooks]]"]
    hooks, carried = [], []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        body = lines[start + 1:end]
        # Comments at the end of a block describe the next hook: they go with it.
        last = max((i for i, line in enumerate(body) if line.strip() and not line.strip().startswith("#")), default=-1)
        trailing = body[last + 1:]
        hooks.append(Hook(part, carried, body[:last + 1], when))
        carried = [line for line in trailing if line.strip()]
    doc = tomllib.loads(path.read_text())
    if len(doc.get("hooks", [])) != len(hooks):
        fail(f"{path}: read {len(hooks)} hooks, TOML has {len(doc.get('hooks', []))}")
    return hooks


def merge_hooks(parts: list[tuple[str, Path, str | None]], off: set[str] | None = None,
                required: list[tuple[str, Path]] = ()) -> tuple[str, int, int]:
    """parts: each part's name, its folder, and the option its hooks depend on, if any.
    off: None for the patch itself, whose hooks carry their conditions; else the options that are
    off, for the list an installer that resolved them writes: those options' hooks left out, and
    no conditions.
    required: the patches this one requires (--split), by name and folder. A hook one of them
    declares identically is theirs and is left out here (KotOR Patch Manager refuses two patches
    that hook one address); one they declare differently stops the build."""
    seen: dict[int, Hook] = {}
    kept: list[Hook] = []
    duplicates = 0
    theirs: dict[int, Hook] = {}
    for part, directory in required:
        for hook in read_hooks(part, directory / HOOKS_FILE):
            theirs[hook.address] = hook
    for part, directory, when in parts:
        for hook in read_hooks(part, directory / HOOKS_FILE, when):
            if hook.address in theirs:
                if theirs[hook.address].key != hook.key:
                    fail(f"{theirs[hook.address].part}, which this patch requires, and {part} hook {hook.address:#x} differently")
                duplicates += 1
                continue
            if hook.address in seen:
                if seen[hook.address].key != hook.key:
                    fail(f"{seen[hook.address].part} and {part} hook {hook.address:#x} differently")
                duplicates += 1
                continue
            seen[hook.address] = hook
            kept.append(hook)
    if off is not None:
        kept = [h for h in kept if h.when not in off]
    ordered = [h for h in kept if h.kind != "detour"] + [h for h in kept if h.kind == "detour"]
    names = ", ".join(part for part, _, _ in parts)
    text = (
        "# KMRP for macOS: one patch, merged by macos/tools/make_kmrp_patch.py from " + names + ".\n"
        "# All byte hooks first, then all detours: the first detour loads the module, whose\n"
        "# constructors rewrite byte hooks already applied (see make_kmrp_patch.py).\n"
        "[metadata]\n"
        f'target_versions = ["{GAME_SHA}"]\n\n'
        + "\n".join(h.text(conditions=off is None) for h in ordered)
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


def controller_patch(args) -> int:
    """KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch: the controller's sources, the two shared sources they need
    (kmrp-layout/text.cpp and options.cpp, the latter reading the controller's own options
    file), and its files in the section __KMRPC,__assets."""
    if not (args.controller and args.sdl and args.controller_bank and args.controller_bank.is_file()):
        fail("--controller-patch needs --controller DIR, --sdl DIR and --controller-bank FILE")
    define = "-DKMRP_CONTROLLER_PATCH"
    with tempfile.TemporaryDirectory(prefix="kmrp-controller-patch-") as tmp:
        tmp = Path(tmp)
        (tmp / "objects").mkdir()
        (tmp / "binaries").mkdir()
        files = sources(args.controller, ("*.cpp", "*.mm"))
        if not files:
            fail(f"no sources in {args.controller}")
        objects = compile_part(files, [*CONTROLLER_FLAGS, define, "-F", str(args.sdl)], tmp / "objects", "kmrp-controller")
        objects += compile_part([args.layout / "text.cpp", args.layout / "options.cpp"], [*LAYOUT_FLAGS, define],
                                tmp / "objects", "shared")
        module = tmp / "binaries" / "macos_x86_64.dylib"
        link = ["clang++", *LINK_FLAGS, *CONTROLLER_LINK, "-F", str(args.sdl), "-lz",
                f"-Wl,-sectcreate,__KMRPC,__assets,{args.controller_bank}", "-o", str(module), *map(str, objects)]
        result = subprocess.run(link, capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"the controller module does not link\n{result.stderr}")
        subprocess.run(["codesign", "--force", "--sign", "-", str(module)], check=True, capture_output=True)
        hooks = read_hooks("kmrp-controller", args.controller / HOOKS_FILE)
        addresses = [h.address for h in hooks]
        if len(set(addresses)) != len(addresses):
            fail("the controller's hook list names an address twice")
        ordered = [h for h in hooks if h.kind != "detour"] + [h for h in hooks if h.kind == "detour"]
        (tmp / HOOKS_FILE).write_text(
            "# The controller patch for macOS, from macos/patches/kmrp-controller by make_kmrp_patch.py.\n"
            "[metadata]\n"
            f'target_versions = ["{GAME_SHA}"]\n\n' + "\n".join(h.text(conditions=False) for h in ordered))
        (tmp / "manifest.toml").write_text(
            "[patch]\n"
            f'id = "{CONTROLLER_ID}"\n'
            f'name = "{CONTROLLER_NAME}"\n'
            f'version = "{args.version}"\n'
            f'description = "{CONTROLLER_DESCRIPTION}"\n'
            'author = "RaymanGT"\n'
            "requires = []\n"
            "conflicts = [" + ", ".join(f'"{c}"' for c in CONTROLLER_CONFLICTS) + "]\n\n"
            + "".join(
                "[[patch.options]]\n"
                f'id = "{option}"\n'
                f'name = "{name}"\n'
                f'description = "{description}"\n'
                'type = "toggle"\n'
                f"default = {'true' if default else 'false'}\n\n"
                for option, name, default, description in CONTROLLER_OPTIONS) +
            "[patch.supported_versions]\n"
            f'kotor1_steam_aspyr_macos = "{GAME_SHA}"\n')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("manifest.toml", HOOKS_FILE, "binaries/macos_x86_64.dylib"):
                z.write(tmp / name, name)
        order = constructor_order(module)
    print(f"{args.out.name}: the controller patch; {len(hooks)} hooks; {len(order)} constructors; options "
          + ", ".join(option for option, *_ in CONTROLLER_OPTIONS))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for name in ("widescreen", "stray"):
        parser.add_argument(f"--{name}", type=Path,
                            help="FTD's patch source; with --split only its hooks are read, to leave out "
                                 "of KMRP what that patch already declares")
    for name in ("layout", "notes", "notes-include"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--controller", type=Path, help="patches/kmrp-controller, for --controller-patch")
    parser.add_argument("--sdl", type=Path, help="the SDL3 framework's folder, for --controller-patch")
    parser.add_argument("--controller-patch", action="store_true",
                        help="the controller patch instead of KMRP's: KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch, a patch of its "
                             "own with its files inside (--controller-bank)")
    parser.add_argument("--controller-bank", type=Path, help="the bank make_controller_assets.py packed")
    parser.add_argument("--split", action="store_true",
                        help="KMRP's own code only, as a patch that requires FTD's two patches")
    parser.add_argument("--version", required=True)
    parser.add_argument("--no-map-notes", action="store_true")
    parser.add_argument("--options", action="store_true",
                        help="the optional parts as patch options instead of build flags")
    parser.add_argument("--assets", type=Path, help="patches/kmrp-assets: the menu sets inside the module")
    parser.add_argument("--assets-bank", type=Path, help="the bank make_kmrp_assets.py packed")
    parser.add_argument("--tools", type=Path, help="macos/tools, for the helpers the assets part calls")
    parser.add_argument("--without-option", action="append", default=[], metavar="ID",
                        help="with --options: the patch as an installer that resolved the options "
                             "installs it with this one off, for staging its hook list only")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.controller_patch:
        return controller_patch(args)
    if args.options and args.no_map_notes:
        fail("--options builds the whole patch; it does not go with --no-map-notes")
    off = set(args.without_option) if args.without_option else None
    if off is not None and (not args.options or off - {option for option, *_ in OPTIONS}):
        fail("--without-option goes with --options and names one of " + ", ".join(option for option, *_ in OPTIONS))

    if args.split and not (args.options and args.assets):
        fail("--split builds the patch with options and the menu sets: it needs --options and --assets")
    if not args.split and not (args.widescreen and args.stray):
        fail("--widescreen and --stray are needed unless --split")
    with_assets = bool(args.assets)
    if with_assets and not (args.assets_bank and args.tools and args.assets_bank.is_file()):
        fail("--assets needs --assets-bank FILE and --tools DIR")
    # The assets part first: its constructor has to run before the widescreen patch's.
    # ... and its Retina mode scale under another name: kmrp-assets/resolution.cpp has the hook's
    # function, which lists the display's pixel modes whatever size the game starts at.
    widescreen_flags = ([*FTD_FLAGS, "-Dfopen=kmrp_ini_fopen", "-DKMRP_DisplayModeScale=KMRP_DisplayModeScale_widescreen"]
                        if with_assets else FTD_FLAGS)
    if args.split:
        # KMRP's own code only. FTD's two patches are patches of their own, which this one
        # requires; the assets part asks the widescreen patch for its .gui mode by its entry
        # points (kmrp-assets/widescreen.cpp).
        parts = [("kmrp-assets", args.assets, LAYOUT_FLAGS, ("*.cpp",)),
                 ("kmrp-layout", args.layout, LAYOUT_FLAGS, ("*.cpp",))]
    else:
        parts = ([("kmrp-assets", args.assets, [*LAYOUT_FLAGS, "-DKMRP_BUNDLED_WIDESCREEN"], ("*.cpp",))] if with_assets else []) + [
             ("K1WidescreenPatch", args.widescreen, widescreen_flags, ("*.cpp",)),
             ("K1StrayBugFixes", args.stray, FTD_FLAGS, ("*.cpp",)),
             ("kmrp-layout", args.layout, LAYOUT_FLAGS, ("*.cpp",))]
    if not args.no_map_notes:
        parts.append(("kmrp-map-notes", args.notes, [*LAYOUT_FLAGS, "-I", str(args.notes_include)], ("*.cpp",)))

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
        assets_link = []
        if with_assets:
            for name, define in HELPERS:
                objects += compile_part([args.tools / name], [*HELPER_FLAGS, define], tmp / "objects", "helper")
            assets_link = ["-lz", f"-Wl,-sectcreate,__KMRP,__assets,{args.assets_bank}"]
        module = tmp / "binaries" / "macos_x86_64.dylib"
        link = ["clang++", *LINK_FLAGS, *assets_link, "-o", str(module), *map(str, objects)]
        result = subprocess.run(link, capture_output=True, text=True)
        if result.returncode != 0:
            fail(f"the module does not link\n{result.stderr}")
        subprocess.run(["codesign", "--force", "--sign", "-", str(module)], check=True, capture_output=True)

        order = constructor_order(module)
        ftd, layout = first(order, "DylibInit"), first(order, "ApplyLayoutSupport")
        if args.split:
            # The assets part's constructor asks the widescreen patch for its .gui mode and tells
            # kmrp-layout to wait for it, so it has to run before kmrp-layout's.
            if ftd >= 0:
                fail(f"--split must not carry FTD's code; the module runs {order}")
            if layout < 0 or not 0 <= first(order, "UseKmrpIni") < layout:
                fail(f"the assets part's UseKmrpIni must run before KMRP's ApplyLayoutSupport; the module runs {order}")
        else:
            if ftd < 0 or layout < 0 or ftd > layout:
                fail(f"FTD's DylibInit must run before KMRP's ApplyLayoutSupport; the module runs {order}")
            if with_assets and not 0 <= first(order, "UseKmrpIni") < ftd:
                fail(f"the assets part's UseKmrpIni must run before FTD's DylibInit; the module runs {order}")

        hook_parts = [(part, directory, PART_OPTION.get(part) if args.options else None)
                      for part, directory, _, _ in parts]
        required = [(name, directory) for name, directory in
                    (("K1StrayBugFixes", args.stray), ("K1WidescreenPatch", args.widescreen))
                    if args.split and directory]
        hooks, count, duplicates = merge_hooks(hook_parts, off, required)
        (tmp / HOOKS_FILE).write_text(hooks)
        included = ", ".join(part for part, *_ in parts)
        (tmp / "manifest.toml").write_text(
            "[patch]\n"
            'id = "kmrp"\n'
            'name = "KMRP for macOS"\n'
            f'version = "{args.version}"\n'
            + ('description = "KMRP in one patch, on FTD\'s Widescreen Patch and Stray Bug Fixes, which it '
               'requires: tick those two as well. The high-resolution interface for every resolution this '
               'display offers, chosen in Options; the map notes are an option you can turn '
               'off. Controller support is a patch of its own, KOTOR 1 Native Controller Mod, which works '
               'beside this one. Needs no installer and writes nothing to the game\'s override folder."\n' if args.split else
               f'description = "KMRP for macOS as one patch: {included}. FTD\'s Widescreen Patch and Stray Bug '
            "Fixes (MIT) built from their source with KMRP's layout support and options linked in. It includes "
            'those two patches: untick them. '
            + ("The menu layouts for every resolution are inside: it needs no installer and writes nothing to "
               "the game's override folder." if with_assets else
               "Run through KMRP Installer, which adds the menu layouts.") + '"\n')
            # The maintainer's credit (2026-10-01): RaymanGT, with FTD, who laid the foundation
            # KMRP for macOS is built on. FTD's own manifest also names J and Vriff.
            + ('author = "RaymanGT"\n' if args.split else 'author = "RaymanGT, FTD"\n')
            # It carries FTD's two patches, so KPM must not apply them beside it: the conflict
            # KMRP.kpatch declares on Windows with the KPM patches making KMRP's fixes (2026-10-01).
            + ('requires = ["k1-stray-bug-fixes-patch", "k1widescreenpatch"]\nconflicts = []\n\n' if args.split else
               'requires = []\nconflicts = ["k1widescreenpatch", "k1-stray-bug-fixes-patch"]\n\n')
            + ("".join(
                "[[patch.options]]\n"
                f'id = "{option}"\n'
                f'name = "{name}"\n'
                f'description = "{description}"\n'
                'type = "toggle"\n'
                f"default = {'true' if default else 'false'}\n\n"
                for option, name, default, description in OPTIONS) if args.options and off is None else "") +
            "[patch.supported_versions]\n"
            f'kotor1_steam_aspyr_macos = "{GAME_SHA}"\n')
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("manifest.toml", HOOKS_FILE, "binaries/macos_x86_64.dylib"):
                z.write(tmp / name, name)
    if args.options:
        included += "; options " + ", ".join(option for option, *_ in OPTIONS)
        if off is not None:
            included += "; resolved with " + ", ".join(sorted(off)) + " off, for staging"
    print(f"{args.out.name}: {included}; {count} hooks ({duplicates} duplicates dropped); {len(order)} constructors, "
          + ("requires FTD's two patches" if args.split else f"FTD's DylibInit {ftd + 1}, KMRP's ApplyLayoutSupport {layout + 1}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
