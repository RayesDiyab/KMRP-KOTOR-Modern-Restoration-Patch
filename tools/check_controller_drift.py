#!/usr/bin/env python3
"""Fail loudly when the controller patch's sources of truth disagree.

Every check here exists because the disagreement it looks for actually happened
and was reported as a defect in the game rather than in the tooling:

  1. A hook in kotor1.hooks.toml whose export no source defines. Ownership is
     derived from the defining .cpp, so an unresolvable hook would silently
     become "not KMRP's" -- the same failure mode as the prefix list this
     replaced, which mis-classified NativeGuiFrameK1 and then
     NativeCameraFrameK1.
  2. A hook missing from exports.def, which links but cannot be resolved at
     patch time.
  3. Installed native hooks that differ from the tracked table. The installer
     used to carry its own copy of that table, so the game could be running hooks
     no tracked file described.
  4. A constant the tests import that the module no longer defines. The tests
     used to hardcode copies; a copy that outlives its original reports a
     correct module as broken.

Exit status is 0 when everything agrees, 1 otherwise.

Usage:
    python tools/check_controller_drift.py [--config PATH]

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kmrp_controller as kc                              # noqa: E402

DEFAULT_CONFIG = Path(r"C:\Star Wars - KotOR\patch_config.toml")

# Constants the test scripts and diagnostics import by name. Listed here so that
# deleting or renaming one in the module is caught by this check rather than by a
# traceback in the middle of a 20-minute end-to-end run.
REQUIRED_CONSTANTS = [
    "K1_STICK_DEADZONE",
    "K1_CAMERA_DEADZONE",
    "K1_CAMERA_SPEED",
    "K1_NAV_STICK_ENGAGE",
    "K1_NAV_STICK_RELEASE",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="installed patch_config.toml (skipped when absent)")
    arguments = parser.parse_args()

    problems = []
    hooks = kc.hooks()
    print(f"{len(hooks)} hooks in {kc.HOOKS_TOML.name}")

    # 1. every hook classifiable
    unowned = [h["function"] for h in hooks
               if h["owner"] is None and not kc.is_byte_patch(h)]
    if unowned:
        problems.append(
            "no tracked source defines these hook exports, so their owner cannot "
            f"be derived: {', '.join(unowned)}")
    native = [h for h in hooks if h["owner"] == kc.KMRP]
    legacy = [h for h in hooks if h["owner"] == kc.LEGACY]
    print(f"  {len(native)} KMRP native, {len(legacy)} legacy, {len(unowned)} unowned")

    # What the installer must emit, which is NOT the same question as who wrote
    # each hook: kc.native_hooks() adds kc.REQUIRED_LEGACY, the legacy-owned
    # hooks the native path depends on. Asked of kmrp_controller rather than
    # recomputed here, because this file having its own copy of the rule is why
    # it failed a correct installer the first time a hook joined that set.
    required = kc.native_hooks()
    required_names = {h["function"] for h in required
                      if not kc.is_byte_patch(h)}
    extra = sorted(required_names - {h["function"] for h in native
                                     if not kc.is_byte_patch(h)})
    if extra:
        print(f"  plus {len(extra)} required legacy: {', '.join(extra)}")

    # 2. every hook exported
    exported = {line.strip() for line in
                kc.EXPORTS_DEF.read_text(encoding="utf-8").splitlines()}
    missing = [h["function"] for h in hooks
               if not kc.is_byte_patch(h) and h["function"] not in exported]
    if missing:
        problems.append(f"hooks missing from exports.def: {', '.join(missing)}")

    # 3. installed native hooks match the tracked table
    if arguments.config.exists():
        installed = kc.installed_hooks(arguments.config)
        # An install without controller support carries the core set, which is
        # told apart by its stand-ins (install = "no-controller").
        stand_ins = {h["function"] for h in kc.installable_hooks()
                     if kc.install_of(h) == "no-controller"}
        expected = (kc.core_hooks()
                    if any(h.get("function") in stand_ins for h in installed)
                    else required)
        expected_names = {h["function"] for h in expected
                          if not kc.is_byte_patch(h)}
        required_addresses = {h["address"] for h in expected
                              if kc.is_byte_patch(h)}
        installed_native = [h for h in installed
                            if h.get("function") in expected_names | required_names
                            or h["address"] in required_addresses]
        # Compared as sets: KPM keys a detour on its address, so the order
        # hooks appear in the file carries no meaning. The installer appends
        # ClearActionBarControlsK1 after the native ones while the tracked table
        # lists it first, which an order-sensitive comparison reported as drift
        # when nothing had drifted.
        def key(h):
            # A byte patch has no function, so its address and original bytes
            # are its identity -- which is what the runtime keys on anyway.
            return (h["address"], h.get("function", ""),
                    tuple(h["original_bytes"]))

        want = {key(h) for h in expected}
        got = {key(h) for h in installed_native}
        which = "controller off" if expected is not required else "controller on"
        if got and got != want:
            missing = sorted(f"{n} @ {a}" for a, n, _ in want - got)
            extra = sorted(f"{n} @ {a}" for a, n, _ in got - want)
            problems.append(
                f"installed hooks ({which}) differ from kotor1.hooks.toml\n"
                f"    missing from the install: {missing or 'none'}\n"
                f"    not in the tracked table: {extra or 'none'}")
        elif got:
            print(f"  installed config matches the tracked table "
                  f"({len(got)} hooks, {which})")
    else:
        print(f"  {arguments.config} not present; install check skipped")

    # 4. the installer can actually render a config
    #
    # This checks the code path that WRITES the config, not just the table it
    # reads. select_controller_path.apply() referred to a NATIVE_HOOKS constant
    # that the single-source refactor had deleted, so both "native" and "both"
    # raised NameError -- and nothing noticed, because the suite only ever calls
    # report(). A renderer nothing exercises is a renderer nothing tests.
    sys.path.insert(0, str(kc.ROOT / "testing" / "controller"))
    try:
        import select_controller_path as installer
        rendered = installer.native_hooks_toml()
        names = re.findall(r'function\s*=\s*"(\w+)"', rendered)
        want = [h["function"] for h in required if not kc.is_byte_patch(h)]
        if names != want:
            problems.append(f"the installer renders {names}, tracked table is {want}")
        else:
            print(f"  installer renders all {len(names)} native hooks")
    except Exception as error:                       # noqa: BLE001 - report it
        problems.append(f"the installer cannot render a config: {error!r}")

    # 4b. every badge the module asks for is actually built
    #
    # The module swaps a button's BORDER.FILL to one of these resrefs when a
    # controller is active. If the texture was never packaged the button loses
    # its art entirely and draws flat white -- with a mouse it looks perfect,
    # because the mouse path never swaps the fill. That is exactly what shipped:
    # twelve tab-screen badges were generated by a side script straight into a
    # developer's game folder and never entered the patcher, so Inventory,
    # Messages, Journal and Map had blank buttons for every user.
    try:
        import build_controller_prompt_textures as prompts
        built = {target.resref.lower() for target in prompts.PROMPT_TARGETS}
        # A button whose caption changes gets one badge per caption,
        # named <resref><index>, so the module can place the glyph beside
        # each wording instead of beside the longest one.
        for target in prompts.PROMPT_TARGETS:
            key = (target.gui, target.tag)
            if key not in prompts.PER_CAPTION_TARGETS:
                continue
            for index in range(len(prompts.PROMPT_STRREFS.get(key, ()))):
                built.add(f"{target.resref}{index}".lower())
        source = (kc.ROOT / "src" / "controller-native" / "vendor"
                  / "K1XboxControls.cpp").read_text(encoding="utf-8")
        wanted = {name.lower()
                  for name in re.findall(r'"(kmrp[a-z_0-9]+)"', source)}
        unbuilt = sorted(wanted - built)
        orphaned = sorted(built - wanted)
        if unbuilt:
            problems.append(f"badges the module uses but the build never makes: "
                            f"{', '.join(unbuilt)}")
        if orphaned:
            problems.append(f"badges built but never referenced: "
                            f"{', '.join(orphaned)}")
        if not unbuilt and not orphaned:
            print(f"  prompt badges: all {len(wanted)} the module uses are built")
    except Exception as error:                       # noqa: BLE001 - report it
        problems.append(f"cannot compare prompt badges: {error!r}")

    # 5. the controller glyph art actually resolves
    #
    # _load_glyph_art falls back to a procedurally drawn badge when a file is
    # missing, and does it silently. When the art pack moved, the configured
    # directory stopped existing and every badge would have quietly become a
    # drawn disc on the next build -- no error, no warning, just different
    # artwork. This asks the question out loud.
    try:
        sys.path.insert(0, str(kc.ROOT / "tools"))
        import build_controller_prompt_textures as textures
        # Every family is shipped and the module can pick any of them, so a
        # family with missing art is a broken badge set, not an unused one.
        counts = []
        for family, (folder, _) in textures.GLYPH_FAMILIES.items():
            directory = textures.GLYPH_PACK / folder
            if not directory.is_dir():
                problems.append(f"the {family} glyph art directory does not exist: "
                                f"{directory}")
                continue
            present, missing = textures.check_glyph_art(family)
            if missing:
                problems.append(f"{family} glyph art missing, badges would silently "
                                f"fall back to drawn discs: {', '.join(missing)}")
            else:
                counts.append(f"{len(present)} {folder}")
        if len(counts) == len(textures.GLYPH_FAMILIES):
            print(f"  glyph art: all present ({', '.join(counts)})")

        # The fourth resref letter per family lives in two places: the build
        # names the textures with it, the module rewrites to it. Out of step,
        # a detected pad would ask for textures that were never built.
        source = (kc.ROOT / "src" / "controller-native"
                  / "K1NativeJoystick.cpp").read_text(encoding="utf-8")
        found = re.search(r"K1_GLYPH_FAMILY_LETTERS\[\]\s*=\s*\{([^}]*)\}", source)
        module_letters = re.findall(r"'(.)'", found.group(1)) if found else []
        build_letters = [textures.FAMILY_LETTERS[f]
                         for f in ("xbox", "playstation", "switch", "steamdeck")]
        if module_letters != build_letters:
            problems.append(f"controller family letters disagree: module "
                            f"{module_letters}, build {build_letters}")
        else:
            print(f"  family letters: module and build agree ({''.join(build_letters)})")
    except Exception as error:                       # noqa: BLE001 - report it
        problems.append(f"the glyph art could not be checked: {error!r}")

    # 6. constants the tooling imports still exist
    values = kc.constants()
    absent = [name for name in REQUIRED_CONSTANTS if name not in values]
    if absent:
        problems.append(
            f"constants imported by the tests are not defined in "
            f"{kc.MODULE_SOURCE.name}: {', '.join(absent)}")
    else:
        print("  constants: " + ", ".join(
            f"{name}={values[name]}" for name in REQUIRED_CONSTANTS))

    # 4c. every panel with a prompt table can actually be found
    #
    # The badges are applied to whatever FindK1MenuPanel returns, and that walks
    # a whitelist -- IsK1MenuPanel, plus IsK1TitleMenuPanel for the title screen.
    # A panel with a full prompt table that is missing from the whitelist shows
    # no badges at all, and on the modal branch it is worse: that returns null
    # when the top modal is unrecognised, so it suppresses EVERY badge while it
    # is up. Equip and Quest Items shipped in exactly that state -- art, tables,
    # offsets and textures all correct and all unreachable.
    try:
        vendor = (kc.ROOT / "src" / "controller-native" / "vendor"
                  / "K1XboxControls.cpp").read_text(encoding="utf-8")

        def between(start, text):
            body = text[text.index(start):]
            return body[:body.index("\n}")]

        tabled = set(re.findall(
            r"case (K1_\w+_VTABLE):",
            between("const ControllerPromptBinding* GetK1ControllerPrompts", vendor)))
        findable = set(re.findall(
            r"vtable == (K1_\w+_VTABLE)",
            between("bool IsK1MenuPanel", vendor)))
        findable |= set(re.findall(
            r"vtable == (K1_\w+_VTABLE)",
            between("bool IsK1TitleMenuPanel", vendor)))

        unreachable = sorted(tabled - findable)
        if unreachable:
            problems.append(
                "panels carry badges the panel search can never show: "
                + ", ".join(unreachable)
                + " -- add them to IsK1MenuPanel")
        else:
            print(f"  prompt panels: all {len(tabled)} are reachable by the "
                  f"panel search")
    except Exception as error:                       # noqa: BLE001 - report it
        problems.append(f"cannot compare prompt panels: {error!r}")

    # 6. the diagnostic line's conversions match its arguments
    #
    # A conversion was once inserted mid-format with its argument appended at the
    # end of the list, so every field after it printed the wrong variable, and
    # the widened line overran a 512-byte stack buffer and tripped the stack
    # cookie. The game froze on load and the cause looked nothing like logging.
    #
    # The call is parsed by walking parentheses from wsprintfA(, skipping string
    # literals and // comments, because the format's own comments contain both
    # parentheses and semicolons.
    #
    # Found inside the function that writes it, not as the file's first
    # wsprintfA: when another call was added earlier in the file this check went
    # on passing while measuring a one-conversion string instead of the line.
    source = kc.MODULE_SOURCE.read_text(encoding="utf-8")
    try:
        # The definition, not the forward declaration: the body's opening brace.
        start = re.search(r'extern "C" void __cdecl NativeJoystickDumpK1\(\)\s*\{',
                          source).start()
        index = source.index("wsprintfA(", start) + len("wsprintfA(")
    except (ValueError, AttributeError):
        index = -1
        problems.append("cannot find the diagnostic line: no wsprintfA in NativeJoystickDumpK1")
    if index > 0:
        depth = 1
        literals = []
        code = []
        while depth:
            char = source[index]
            if char == '"':
                end = index + 1
                while source[end] != '"' or source[end - 1] == "\\":
                    end += 1
                literals.append(source[index + 1:end])
                index = end + 1
                continue
            if source.startswith("//", index):
                index = source.index("\n", index)
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            code.append(char)
            index += 1

        fmt = "".join(literals)
        conversion = re.compile(r"%[-+ #0-9.]*(?:ll|l|h)?[diouxXeEfgGcsp]")
        conversions = conversion.findall(fmt)

        depth = 0
        arguments = 1
        for char in "".join(code):
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            elif char == "," and depth == 0:
                arguments += 1
        # The buffer, and the empty slot the format literal leaves behind.
        arguments -= 2

        if len(conversions) != arguments:
            problems.append(
                f"the diagnostic line has {len(conversions)} conversions but "
                f"{arguments} arguments; a field added mid-format needs its "
                f"argument in the matching position, not at the end")
        else:
            widest = len(conversion.sub("4294967295", fmt))
            size = re.search(r"char line\[(\d+)\]", source)
            capacity = int(size.group(1)) if size else 0
            if capacity and widest >= capacity:
                problems.append(
                    f"the diagnostic line can reach {widest} bytes in a "
                    f"{capacity}-byte buffer")
            else:
                print(f"  diagnostic line: {len(conversions)} conversions, "
                      f"{arguments} arguments, worst case ~{widest} of "
                      f"{capacity} bytes")

    print()
    if problems:
        for problem in problems:
            print("DRIFT: " + problem)
        return 1
    print("No drift: hooks, ownership, exports and constants all agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
