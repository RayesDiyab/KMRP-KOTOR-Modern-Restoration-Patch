# The KMRP controller module

This directory is the **canonical, authoritative source** for
`kmrp-controller.module`. Project sources are tracked here; SDL headers come from a hash-verified SDK
under ignored `build/deps`.

Build it with `build.cmd` (Visual Studio Build Tools, x86, and PowerShell 7).
The script prepares the pinned SDL SDK automatically. See
[the hybrid backend reference](../../docs/controller-sdl-backend.md). The output,
`kmrp-controller.module`, is what `build_kmrp.ps1` embeds in the installer as
`Kmrp.controller.module` -- in the 2026-09-24 installer, 181,248 bytes, SHA-256
`AC2C41EC4C935B19EFF4693E3FBB43D176D28C5B37DE0CDC2C706F72379652C9`; in the
2026-09-25 installer (`B599303A…`), SHA-256 `DC06F697EE284D93425DCF3FFC965104DCBCD4B9AF681EF4FDD48AEB765CE807`,
with the dialogue A and two navigation fixes -- and what
`testing/controller/select_controller_path.py` installs into a test game. The
reverse engineering behind the native path is in
`reverse-engineering/retained-xbox-gui-events.md`; the architecture and the full
mapping are in `docs/controller-native-path.md`.

| File | Whose | What |
| --- | --- | --- |
| `K1ControllerBackend.cpp` / `.h` | KMRP | XInput and SDL/HIDAPI state normalization, active-device selection and rumble |
| `K1ControllerLayout.cpp` / `.h` | KMRP | Options → Gameplay entry, modal Controller Layout panel, live glyph refresh, callbacks and explicit control ownership |
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

The upstream project is MIT, and KMRP ships it as an Advanced Settings
component -- opt-in until 2026-09-24, on by default since -- with full
attribution; see `THIRD_PARTY_NOTICES.md`. So the modified sources are tracked
here, and the delta against upstream stays readable as
`third_party/Included/KPM-Xbox-Controls-K1-1.2 by Saul0097/KMRP-CONTROLLER-MODULE.diff`,
the convention this repository already used for its changes to that project.

The clone under `build/research/` is left pristine and is **not** part of the
build. **Regenerate the diff whenever the five files change**, not only after an
upstream update: copy upstream's `K1XboxControls.cpp`,
`K1XboxControlsXInput.cpp`, `K1XboxControlsXInput.h`, `exports.def` and
`kotor1.hooks.toml` into an empty git repository and commit them, copy ours over
the top (the vendor files from `vendor/`), and write `git diff` to that file.
Applying it to a checkout of upstream commit `78e7eaa` must reproduce all five
exactly.

*Corrected 2026-09-24:* this section named `KMRP-RUNTIME-PATCH.diff` as the
vendor delta. That file is the KOTOR Patch Manager runtime's 16-line
`SelfModuleDir` patch; commit `2f2206c` had overwritten it with the vendor delta,
which was never regenerated after and had fallen hundreds of lines behind these
files. The runtime patch is restored, and the vendor delta has its own file,
regenerated and checked to reproduce the five files.
