# The KMRP controller module

This directory is the **canonical, authoritative source** for
`kmrp-controller.module`. Everything the build compiles is tracked here.

Build it with `build.cmd` (Visual Studio Build Tools, x86). The output,
`kmrp-controller.module`, is what `testing/controller/select_controller_path.py`
installs. The reverse engineering behind the native path is in
`reverse-engineering/retained-xbox-gui-events.md`; the architecture and the full
mapping are in `docs/controller-native-path.md`.

| File | Whose | What |
| --- | --- | --- |
| `K1NativeJoystick.cpp` / `.h` | KMRP | the native path: supplies the joystick device KOTOR's retained console input system expects, so the engine's own handlers drive movement, buttons, menus, camera and free look |
| `vendor/K1XboxControls.cpp` | Saul0097, modified by KMRP | movie skipping, the action bar, focus fixes, cursor and device-switch policy |
| `vendor/K1XboxControlsXInput.cpp` / `.h` | Saul0097, modified by KMRP | XInput reading and the last-input-device state the prompts depend on |
| `exports.def` | KMRP | the module's exports, including the native hooks |
| `kotor1.hooks.toml` | Saul0097, modified by KMRP | hook addresses, including the native entries |

## Why the vendor files are copied in rather than referenced

They used to be compiled straight out of a clone of Saul0097's repository under
`build/research/KPM-Xbox-Controls-K1/`, which is ignored by this repository's
`.gitignore`. That meant the build's real inputs were untracked: roughly 900
lines of KMRP's own module, and about 840 lines of KMRP modifications to
Saul0097's files, existed only as working-tree edits inside somebody else's
checkout, with his GitHub as the only remote in reach. A `git clean -xfd`, or
simply re-cloning, would have destroyed all of it.

The upstream project is MIT, and KMRP already ships it as an opt-in component
with full attribution -- see `THIRD_PARTY_NOTICES.md`. So the modified sources
are tracked here, and the delta against upstream stays readable as
`third_party/Included/KPM-Xbox-Controls-K1-1.2 by Saul0097/KMRP-RUNTIME-PATCH.diff`,
which is the convention this repository already used for its other changes to
that project.

The clone under `build/research/` is now left pristine and is **not** part of the
build. To refresh the vendor delta after an upstream update, apply these files
over a fresh clone and regenerate that diff.
