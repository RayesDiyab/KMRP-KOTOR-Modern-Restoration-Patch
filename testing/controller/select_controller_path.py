#!/usr/bin/env python3
"""Switch the installed game between the controller input paths, for testing.

Two implementations currently coexist. The older one synthesises keystrokes from
XInput and drives everything -- buttons, menus, both sticks. The newer one feeds
XInput into KOTOR's own retained joystick pipeline and currently drives left
stick movement only. While both are installed they overlap, which makes it hard
to attribute a symptom to either.

All of the older path's controller input is driven from exactly one place:
`PollXInputK1()` is called only from `DispatchMenuInputK1`, which is hooked at
`ProcessInput`. Dropping that one hook silences the whole of it, so the modes
below differ only in which hooks the config lists -- no rebuild is involved and
nothing is destroyed.

    saul      the shipping configuration: 8 hooks, no native path
    native    the 4 native hooks alone, so movement can be judged in isolation
    both      all 12, which is what a finished patch would install

Usage:
    python testing/controller/select_controller_path.py [saul|native|both]
    python testing/controller/select_controller_path.py            # report only

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tomllib
from pathlib import Path

GAME = Path(r"C:\Star Wars - KotOR")
CONFIG = GAME / "patch_config.toml"
MODULE = GAME / "kmrp-controller.module"

# The shipping configuration, saved before any of this work began.
BASELINE_CONFIG = GAME / "patch_config.toml.pre-native-joystick"
BASELINE_MODULE = GAME / "kmrp-controller.module.pre-native-joystick"

# The build carrying the native joystick code. It also contains every one of the
# older path's exports, so it serves all three modes.
#
# Built by src/controller-native/build.cmd from tracked source only. It used to
# come out of the clone of Saul0097's repository under build/research/, which
# was the sole copy of both KMRP's own module and its changes to his.
NATIVE_MODULE = Path(__file__).resolve().parents[2] / (
    "src/controller-native/kmrp-controller.module")

NATIVE_HOOKS = """
[[patches.hooks]]
address = 0x005E24E0
type = "detour"
function = "NativeJoystickInitK1"
original_bytes = [0x6A, 0xFF, 0x68, 0xFD, 0x48, 0x72, 0x00]
skip_original_bytes = false
exclude_from_restore = []
[[patches.hooks.parameters]]
source = "ecx"
type = "pointer"

[[patches.hooks]]
address = 0x005E30F6
type = "detour"
function = "NativeJoystickBufferK1"
original_bytes = [0x89, 0x5C, 0x24, 0x2C, 0x74, 0x0F]
skip_original_bytes = true
exclude_from_restore = ["eax"]
consumed_exit_address = 0x005E319B
[[patches.hooks.parameters]]
source = "esi"
type = "pointer"

[[patches.hooks]]
address = 0x00679940
type = "detour"
function = "NativeJoystickMovementK1"
original_bytes = [0xD9, 0x05, 0x64, 0xD7, 0x73, 0x00]
skip_original_bytes = false
exclude_from_restore = []
[[patches.hooks.parameters]]
source = "ecx"
type = "pointer"

[[patches.hooks]]
address = 0x00679B71
type = "detour"
function = "NativeJoystickSkipNormalizeK1"
original_bytes = [0xE8, 0xBA, 0x15, 0xE3, 0xFF]
skip_original_bytes = true
exclude_from_restore = ["eax"]
consumed_exit_address = 0x00679B76
[[patches.hooks.parameters]]
source = "ecx"
type = "pointer"

[[patches.hooks]]
address = 0x0040CE70
type = "detour"
function = "NativeGuiFrameK1"
original_bytes = [0x51, 0x53, 0x55, 0x56, 0x8B, 0xE9]
skip_original_bytes = false
exclude_from_restore = []
[[patches.hooks.parameters]]
source = "ecx"
type = "pointer"
"""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16] if path.exists() else "missing"


def header_only(text: str) -> str:
    """The config down to, but not including, its first hook."""
    marker = "[[patches.hooks]]"
    return text[:text.index(marker)] if marker in text else text


def report() -> None:
    if not CONFIG.exists():
        print("no patch_config.toml installed")
        return
    with CONFIG.open("rb") as handle:
        hooks = tomllib.load(handle)["patches"][0]["hooks"]
    # "Native" means KMRP's own path, which is more than the joystick hooks:
    # NativeGuiFrameK1 carries the focus-navigation layer. Matching only on the
    # NativeJoystick prefix counted it as one of Saul's and reported mode "both"
    # on a clean native install.
    def is_native(hook):
        return hook["function"].startswith(("NativeJoystick", "NativeGui"))

    native = [h for h in hooks if is_native(h)]
    older = [h for h in hooks if not is_native(h)]
    mode = ("both" if native and older else
            "native" if native else
            "saul" if older else "none")
    print(f"mode: {mode}   ({len(older)} legacy hooks, {len(native)} native)")
    print(f"  config  {digest(CONFIG)}")
    print(f"  module  {digest(MODULE)}")
    if mode in ("native", "both"):
        print("  note: the older path's controller input is driven only from")
        print("        DispatchMenuInputK1; its absence silences all of it.")


def apply(mode: str) -> int:
    for required in (BASELINE_CONFIG, BASELINE_MODULE):
        if not required.exists():
            print(f"missing baseline: {required}")
            return 1

    baseline = BASELINE_CONFIG.read_text()

    if mode == "saul":
        shutil.copyfile(BASELINE_CONFIG, CONFIG)
        shutil.copyfile(BASELINE_MODULE, MODULE)
    elif mode == "both":
        if not NATIVE_MODULE.exists():
            print(f"native module not built: {NATIVE_MODULE}")
            return 1
        CONFIG.write_text(baseline.rstrip("\n") + "\n" + NATIVE_HOOKS)
        shutil.copyfile(NATIVE_MODULE, MODULE)
    elif mode == "native":
        if not NATIVE_MODULE.exists():
            print(f"native module not built: {NATIVE_MODULE}")
            return 1
        # Keep the header -- target_version_sha, patch id, dll name -- and drop
        # every legacy hook, which removes DispatchMenuInputK1 and with it all of
        # the older path's controller input.
        CONFIG.write_text(header_only(baseline).rstrip("\n") + "\n" + NATIVE_HOOKS)
        shutil.copyfile(NATIVE_MODULE, MODULE)
    else:
        print(f"unknown mode: {mode}")
        return 1

    print(f"switched to '{mode}'")
    report()
    print("\nRestart KOTOR for this to take effect.")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        report()
        print("\nusage: select_controller_path.py [saul|native|both]")
        return 0
    return apply(sys.argv[1].lower())


if __name__ == "__main__":
    raise SystemExit(main())
