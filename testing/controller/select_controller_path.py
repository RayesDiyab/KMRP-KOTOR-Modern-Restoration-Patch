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

    saul      the shipping configuration: the legacy hooks, no native path
    native    KMRP's native hooks alone, so movement can be judged in isolation
    both      every hook, which is what a finished patch would install

The counts are deliberately not written down; they were wrong here for two
hooks' worth of history. `report()` prints what is actually installed.

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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import kmrp_controller                                    # noqa: E402

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

# The native hook table is NOT restated here. It is rendered from
# src/controller-native/kotor1.hooks.toml, which is the file the patch is
# actually built from. This used to be a second hand-maintained copy, so
# adding one hook meant editing the same addresses in three places, and
# forgetting one of them is how NativeCameraFrameK1 came to be classified as
# a legacy hook by the test suite.
def native_hooks_toml() -> str:
    return kmrp_controller.render_patch_hooks(kmrp_controller.native_hooks())


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
    # Ownership is derived from which .cpp defines the export, so a new hook
    # classifies itself. The prefix list this replaces was wrong twice: once for
    # NativeGuiFrameK1 and again for NativeCameraFrameK1, each time reporting
    # mode "both" on a clean native install.
    native = [h for h in hooks if kmrp_controller.is_native(h["function"])]
    older = [h for h in hooks if not kmrp_controller.is_native(h["function"])]
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
