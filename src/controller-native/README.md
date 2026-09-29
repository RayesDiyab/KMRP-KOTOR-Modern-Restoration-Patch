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
with the dialogue A and two navigation fixes; in the installer `873A01E2…`,
SHA-256 `E0B62065A20ACC8D957B081EA14F57B5CA5FE62DF1BDF21980F919D590B2B680`,
which adds BioWare's rumble table; in the hardware-test installer `C796489A…`,
204,288 bytes, SHA-256 `E52826A2724038E765DFD45B86171160A017E054E346E29CF4A1CE5D0F74DE21`,
which adds the rumble mixer and Enhanced haptics (`K1Rumble.cpp`); in the
installers `D58A2E33…`, `7C2FFF8B…` and `AD3DC07D…`, 204,800 bytes, SHA-256
`577AAE92D0FE18766EDEC669C54959A0213BA1618030F4E1B0EED92E4D9CC251`, which adds X and Y in combat and
moves the dialogue A to the end of the reply; in the installer `E5AFC981…`,
205,824 bytes, SHA-256 `32F018CFE3D93AE9C9C5F4D20DDCB85FE422DD09EECAC798F13263F03BA43E9C`,
which places that A from the drawn layout; in `EC98B10F…`, 206,336 bytes,
SHA-256 `628D4DC244535E26E4EBD81F4DC4710691A60CC19A6885735F66AF551BB10F90`, which adds the
character-creation A guard; in `1720E0C1…`, 209,408 bytes, SHA-256
`B7307208D5C2B93B86821DC9746E39EEE8C84B17D09919AD7EFD4171D37E0D59`, which adds the
character-creation badges and the Attributes/Skills navigation; in `DB9D7A08…`,
209,920 bytes, SHA-256 `B28A80F7B635595A59651458E2D35AB20145BCD62EBC5DFC3DE4CDF72696B43B`,
which adds Feats' A/X swap, the name-entry guard and the dialogue A adjustment,
and is unchanged in `4EF3C181…`; in `D407BF3A…`, 216,576 bytes, SHA-256
`36D23D9B89039E2FB16C69CF3676F919676B2DDD2482E8DFC14C7794E51819C9`,
which adds the settings screens' Y on Default, D-pad on -/+ rows and arrow
glyphs, Pazaak's wager, the dialogue A on its line and the status summary's
layout; in `80616FE6…`, 217,600 bytes, SHA-256
`CB61BF176471DA5E24E415CFFAD4B90E501D01A0FB524D9FBE9FA216AF988020`,
which adds the status summary's A, keeps the D-pad off its OK and counts the
font's spacing in its line width; in `128CDC79…`, 218,112 bytes, SHA-256
`C19CC7725DCBBDAF79E76AADA9F0139CC9A06C2D7759A259AC186F190C424A8C`, which
adds the Level Up, Auto Level Up and skill-info notice badges and keeps the
D-pad off the Character screen; in `9736B41F…`, 217,600 bytes, SHA-256
`69E1811B33EFB36284A1D4CA2CA35D972EC5BEE521E763D46051BB40A254941A`, which
adds the echo guard on every panel (`GuardPanelEchoK1`, the 33rd native hook,
and A pressing a focused button that presses its panel) and drops the D-pad
glyphs on the -/+ arrows -- and what
`testing/controller/select_controller_path.py` installs into a test game. The
reverse engineering behind the native path is in
`reverse-engineering/retained-xbox-gui-events.md`; the architecture and the full
mapping are in `docs/controller-native-path.md`.

| File | Whose | What |
| --- | --- | --- |
| `K1ControllerBackend.cpp` / `.h` | KMRP | XInput and SDL/HIDAPI state normalization, active-device selection and rumble |
| `K1ControllerLayout.cpp` / `.h` | KMRP | Options → Gameplay entry, modal Controller Layout panel, live glyph refresh, callbacks and explicit control ownership |
| `K1NativeJoystick.cpp` / `.h` | KMRP | the native path: supplies the joystick device KOTOR's retained console input system expects, so the engine's own handlers drive movement, buttons, menus, camera and free look |
| `K1Rumble.cpp` / `.h` | KMRP | rumble: BioWare's 22-row `rumble.2da`, KMRP's `KMRP_…` patterns, the mixer that plays both, and the hooks that feed it (`docs/controller-rumble.md`) |
| `vendor/K1XboxControls.cpp` | Saul0097, modified by KMRP | movie skipping, the action bar, focus fixes, cursor and device-switch policy |
| `vendor/K1XboxControlsXInput.cpp` / `.h` | Saul0097, modified by KMRP | XInput reading and the last-input-device state the prompts depend on |
| `exports.def` | KMRP | the module's exports, including the native hooks |
| `kotor1.hooks.toml` | Saul0097, modified by KMRP | hook addresses, including the native entries |

`vendor/` names where the files came from, not whose most of the module is: by
the measurement in `THIRD_PARTY_NOTICES.md` (2026-09-29), 74% of the module's
C++ (9,986 of 13,563 lines) and 38 of its 44 hooks are KMRP's. Even inside the
three `vendor/` files, 1,843 of 5,420 lines are KMRP additions.

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

Two traps, both hit on 2026-09-25. Write the diff with `git diff
--output=<file>`, never through a PowerShell pipe or `$(...)`: PowerShell strips
the carriage returns from captured lines, and the result no longer applies.
And leave `core.autocrlf` at this machine's `true` in the scratch repository:
forcing it off changes every upstream blob hash in the diff's `index` lines,
because upstream's files are CRLF, and turns line endings into content changes.
With `true`, the round trip writes `exports.def` with CRLF where the tracked copy
is LF, so compare that one file with line endings ignored.

*Corrected 2026-09-24:* this section named `KMRP-RUNTIME-PATCH.diff` as the
vendor delta. That file is the KOTOR Patch Manager runtime's 16-line
`SelfModuleDir` patch; commit `2f2206c` had overwritten it with the vendor delta,
which was never regenerated after and had fallen hundreds of lines behind these
files. The runtime patch is restored, and the vendor delta has its own file,
regenerated and checked to reproduce the five files.
