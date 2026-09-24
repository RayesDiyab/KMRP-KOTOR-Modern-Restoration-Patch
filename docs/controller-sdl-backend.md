# Hybrid controller backend

This reference follows the [documentation standard](documentation-standard.md).
It describes the development implementation in
[`K1ControllerBackend.cpp`](../src/controller-native/K1ControllerBackend.cpp).
Compilation and installer tests are separate from runtime and hardware coverage.

## Implementation

Xbox remains on Windows XInput. The optional controller installation also carries
the official SDL 3.4.16 **x86** library as `kmrp-sdl3.dll`, plus its zlib licence.
SDL opens mapped gamepads, and KMRP identifies the device it actually reads using
SDL's gamepad type and vendor. It does not infer a family from unrelated HID
devices connected to the computer.

| Input source | Normalization / glyph family |
| --- | --- |
| XInput | Existing state and slot-specific identity/Steam metadata |
| SDL PS3/PS4/PS5 type | PlayStation |
| SDL Switch Pro / Joy-Con types | Nintendo |
| SDL Valve vendor `0x28DE` | Existing Steam Deck glyph family |
| Other mapped SDL device | Xbox/generic glyph fallback |

The normalized record is `XINPUT_STATE`; higher-level engine events, gameplay
bindings, menus, and prompt resrefs remain the existing ones. SDL face buttons
SOUTH/EAST/WEST/NORTH map to normalized A/B/X/Y. On Nintendo those physical
positions are labelled **B/A/Y/X**; the existing Nintendo glyph table already
accounts for this, so the adapter performs no second letter swap. SDL Y axes are
negated to XInput's up-positive convention, saturating `-32768` to `32767`.
Triggers map `[0,32767]` to `[0,255]`; negative values clamp to zero.

SDL initializes only `SDL_INIT_GAMEPAD`; it creates no game window. Its event
queues are disabled, and the existing game polling calls `SDL_UpdateGamepads`.
XInput, Raw Input, DirectInput, WGI, GameInput, and Xbox HIDAPI are disabled in
SDL so Xbox stays on KMRP's original path. HIDAPI and Valve support are enabled.
`SDL_TIMER_RESOLUTION=0` prevents SDL requesting a finer Windows timer. Enhanced
reports use `auto`, so merely opening a Bluetooth PlayStation pad does not enable
enhanced report mode before an effect needs it. Because SDL owns no window,
background device reads are enabled inside SDL and KMRP suppresses game input
when its process is not foreground.

Connected devices are sampled by the game's existing poll. Discovery and empty
XInput-slot probes are limited to once per second. A newly pressed button, trigger
threshold crossing, or deliberate stick movement can select another connected
pad. Handoff emits a neutral record first, releasing the old device's buttons,
and stops its motors. Stick noise below 8000 does not take ownership. A generation
counter invalidates XInput family identity on reconnect even in the same slot.
Steam virtual-pad metadata is checked once per second, including when the file
was absent initially or is subsequently removed.

Rumble follows the selected backend. XInput retains its two motors; SDL receives
low/high magnitudes with a 1500 ms lease, renewed after 1000 ms while unchanged
nonzero output is needed. Unchanged values are otherwise suppressed. Background
polling sends zero; SDL's lease also bounds vibration if game polling stalls.
No claim is made about DualSense adaptive triggers, gyro, touchpads, or Deck
rear buttons: the existing KMRP mapping exposes none of these.

## Dependency and ownership

[`prepare_sdl3.ps1`](../tools/prepare_sdl3.ps1) downloads the pinned official
[VC SDK release](https://github.com/libsdl-org/SDL/releases/tag/release-3.4.16),
requires archive SHA-256
`1A784CB2A5C64D56FE7A62090FE9D242D9865F235E4EA9678F1A6BA4E693E7DE`,
and verifies the DLL's PE machine is `0x014C`. The SDK remains in ignored
`build/deps`; no binary is added to version control. The module loads only the
adjacent KMRP-named DLL, with dependency lookup restricted to its directory and
System32. An absent/unloadable SDL DLL leaves XInput available.

The existing controller manifest owns the SDL library and licence. A foreign
file at either destination declines the whole controller installation. Restore
removes only matching hashes and accepts only recognized controller filenames;
modified or foreign files remain. The on-disk game executable is unchanged by
this backend.

## Verification and remaining work

Measured on 2026-09-19: MSVC x86 compilation passes. Controller install/restore
passes on isolated fixtures, including byte-for-byte pinned SDL identity, x86
machine type, source/installed TOML equality, foreign-file refusal, and removal
of owned payloads. The source table and patcher agree on 16 detours and four
byte patches after removal of the obsolete renderer-clear workaround.

`Test-SdlBackend.cpp` uses real SDL virtual gamepads and fake XInput calls to
exercise normalization, family selection, handoff, disconnect, and rumble.
**This test has not yet run successfully:** Windows Restart Manager identified
Bitdefender Virus Shield holding the executable open; it was subsequently
removed. A clean x86 test run is required before treating this backend as
validated. No security settings were changed to bypass that block.

Physical Xbox with SDL initialized, DualSense USB/Bluetooth, Switch Pro
USB/Bluetooth, Steam Controller/Deck, translator coexistence, and Proton all
remain untested for this revision. SDL virtual-device tests cannot establish
those hardware results. Steam Controller uses the existing Deck glyph vocabulary;
its different physical controls and default mapping need a real-device check.

The Controller Layout implementation now uses this backend's active family and
input-device state for live presentation. Its resource, callback and ownership
design is documented in [controller-layout.md](controller-layout.md). It is
compiled and structurally verified; the in-game manual acceptance matrix,
including physical family switching, remains outstanding. HUD-release and
Start/Map code already present in the worktree is preserved; its in-game
acceptance test also remains outstanding.

## Verifying by hand

```powershell
cmd /c src\controller-native\build.cmd
cmd /c testing\controller\Test-SdlBackend.cmd
.\build_kmrp.ps1 -ReuseResources
.\testing\regression\Test-ControllerSupport.ps1
python tools/check_patcher_hook_table.py
python tools/check_hook_stolen_bytes.py src/controller-native/kotor1.hooks.toml
```

Then run the hardware matrix above and, on a disposable loaded save, run
`testing/controller/test_hud_release_and_start_map.py`. Check A returns to world
interaction, B cancels HUD focus, Start opens/closes Map, and LT/RT still change
menu tabs. Installation into a live game remains a separate user-requested step.
