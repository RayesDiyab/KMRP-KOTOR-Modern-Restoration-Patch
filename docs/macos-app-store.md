# macOS: the Mac App Store's game

> **Documentation standard.** This document follows
> [`documentation-standard.md`](documentation-standard.md). Read it before editing
> this file, and check the result still meets it -- measured claims only, every
> site tabulated, rejected alternatives and corrections kept visible, and
> anything untested labelled as untested.

> **Work in progress (2026-10-13).** Support for the App Store's game is not finished and is
> not released: the macOS installer on the release is still 1.5.0, for Steam's game. Section
> 7.8 describes a repair that is written and **not yet built or tested**; until it is, the
> game with a save loaded runs at a few frames a second with KMRP. Sections 7.6 to 7.8 are
> the state of the work, not of a release.

**Kind: investigation and what was built from it, 2026-10-12.** The maintainer asked for
"detection and support for the appstore version of the game". Sections 1 to 6 are the
investigation of that morning, kept as written: they end with support shown possible by a
prototype and not built. **Section 7 is what was built the same afternoon** and supersedes
sections 5 and 6 where they say "would" and "not supported yet". Everything was measured on
macOS 27, Apple Silicon, with the game bought and installed from the Mac App Store that
morning; what was not measured says so.

The prototype's files are outside the repository, in `kmrp-macos/work/appstore-20261012/`.
The tools among them are now `macos/tools/appstore/`; the test helpers stayed there
(`runpkg.sh`, which starts the game through the installed app with the devkit; `relay.c`,
which lists and copies files of the game's container from inside its sandbox).

## 1. What the App Store's game is

| | Mac App Store | Steam (the one KMRP supports) |
| --- | --- | --- |
| Bundle | `/Applications/Knights of the Old Republic.app`, owned by root | in the Steam library, the player's |
| Bundle id | `com.aspyr.kotor` | `com.aspyr.kotor.steam` |
| Version | 1.4.1 (build 199106) | 1.4.0 |
| Layout | `Contents/MacOS/AppBundleExe` (Aspyr's launcher), `KOTOR_Exe`, `Assets`, `AspyrAssets`, `_MASReceipt/receipt` | the same but for the receipt |
| `KOTOR_Exe` | thin x86_64, 6,313,504 bytes, SHA-256 `d03315aace822908d6b7ca936d47c644ffe6ebf79822c8c62225bfaaf79ad7ca` | thin x86_64, 6,333,424 bytes, `c1fcb8d3...6d71` |
| Signature | "Apple Mac OS Application Signing", team `VF8SGH77F7`, verifies; flags `0x200 (kill)`, no hardened runtime | Aspyr's, flags none |
| Entitlements, launcher | app-sandbox, application-identifier, team-identifier, application-groups (`VF8SGH77F7.com.aspyr.gg3.sharedprefs`), device.usb, files.user-selected.read-write, network.client | none |
| Entitlements, `KOTOR_Exe` | app-sandbox and `com.apple.security.inherit` only | none |
| Libraries beside it | `libBink2Macx64.dylib`, `gglibsteam_api.dylib` (the launcher's); `KOTOR_Exe` links no Steam library | `libsteam_api.dylib` too |
| Data | sandboxed: `~/Library/Containers/com.aspyr.kotor/Data/` is its home (`HOME` inside the game) | `~/Library/Application Support/Knights of the Old Republic` |

A second download that day, labelled v1.3.8, was not the App Store's game: a 32-bit (`i386`)
build of January 2017 with the Steam bundle id and no signature, which no macOS since 10.15
runs. It was not used.

## 2. The same game at other addresses

`KOTOR_Exe` is the same source compiled without Steam's library. Section by section the two
start at different addresses, each by its own amount (`__TEXT,__text` -0x500, `__DATA,__const`
-0x7020, `__DATA,__data` -0x6d20, `__DATA,__common` +0xba40, `__DATA,__bss` -0xaaee0,
`__TEXT,__const` -0x2d000, `__TEXT,__cstring` +0x35dd0), so no one number moves an address.

Within the code, from Steam's `0x100006e00` on, a function is 0x5600 lower in the App Store's
build; the 0x5100 bytes before that hold code only Steam's has, among other code. At that
distance 78.01% of 4,885,576 bytes are identical; the rest are the operands that name data or
other code.

`translate.py` disassembles both `__text` sections (capstone; 1,294,360 and 1,290,183
instructions), reduces each instruction to a token without what moves (a rip-relative
displacement, a relative branch's target), anchors the two streams on runs of six tokens that
occur once in each file, and extends each anchor while the tokens agree. Result:
1,178,379 instructions mapped (91.0%; 1,112 of them only by position between two anchored
ones), and 97,862 addresses that anchored instructions name mapped to their partners' with
every pair agreeing (55 disputed and left out). 19 seconds.

`lookup.py` answers for one address, and says how: an anchored instruction; a byte inside one;
what an anchored instruction names; data between two such that moved alike (within 64 bytes,
1,024 in a `__DATA` section); data within 64 bytes of one, with the 128 bytes around it
identical in both files at that distance.

| What was translated | Result |
| --- | --- |
| Every `0x100......` literal in the sources of FTD's Widescreen Patch | 424, none failed |
| ... of his Stray Bug Fixes | 4 |
| ... of `macos/patches/kmrp-layout` | 219 |
| ... `kmrp-assets` | 70 |
| ... `kmrp-map-notes` | 1 |
| ... `kmrp-controller` | 407 |
| ... `high-fps-fixes` | 40 |
| The 85 hooks of the three patches staged without the controller (`patch_config.controller-off.toml`) | all: 74 with the same original bytes, 11 with an operand that moved |

Three addresses needed the last two rules: `0x1005a5cb8` and `0x1005aeaa8` (two vtables the
Widescreen Patch compares with; the second confirmed by the function pointer it holds) and
`0x100570efc` (a constant of the feat chain rows). `rewrite_sources.py` stops when an address
outside a comment cannot be translated.

**Not checked:** that structure offsets and vtable slots are the same in both builds (they come
from the same source, and nothing run so far showed otherwise); the byte patterns the modules
compare before they write (`kmrp-layout`'s sites, the Widescreen Patch's), which hold
displacements that differ in the App Store's build: a group whose bytes differ is left alone
by design, so a missing fix would show as that fix missing, not as a crash. `layout-sites.log`
of a run with debug logs would list them; it is in the game's container, which the shell could
not read.

## 3. The bundle cannot be changed

KMRP installs into Steam's game by adding `KotorPatcher.dylib`, `patch_config.toml` and
`patches/` beside `KOTOR_Exe` and one load command to it. In the App Store's game that does not
work, for a reason before any patch:

| Copy of the app (in the work folder) | Launcher |
| --- | --- |
| unchanged | starts, shows its window with PLAY; pressed, the game runs |
| one text file added in `Contents/MacOS`, nothing else | the process exists and runs no code: 0% CPU and 0:00.00 after 33 s, no line from a library inserted into it |
| `KOTOR_Exe` with the load command, re-signed ad hoc with its own two entitlements, and the library beside it | the same |

So it is the bundle no longer matching Apple's seal, not the patcher. What the process waits
for was not established: the system log was not readable from the shell, and a screenshot could
not be taken (macOS asked whether to allow the recording, which was left for the maintainer).
A consent prompt of macOS for another program using the game's container is one explanation;
if so a player could answer it, **not verified**. Whether the game would then pass its receipt
check with a changed `KOTOR_Exe` was not reached either.

Also measured: once the game has run, its container is closed to other programs ("Operation
not permitted" from the shell; it was readable before the first run). An installer writing
`swkotor.ini` or anything else there will be asked about by macOS.

## 4. What does work: nothing changed, the patcher brought in from outside

The launcher and the game have no hardened runtime, so `DYLD_INSERT_LIBRARIES` set when the
launcher is started is honoured, and the launcher passes its environment to `KOTOR_Exe`.
Measured with small test libraries:

| From a library inserted into the unmodified game | |
| --- | --- |
| `HOME` | `~/Library/Containers/com.aspyr.kotor/Data` |
| Read a file in the folder the copy of the app was started from (the work folder) | allowed |
| `dlopen` a library there | allowed |
| Read `~/Library/Application Support/...` of the real home, or `/Users/Shared` | Operation not permitted |
| Write the container's `Library/Caches` and `Library/Application Support` | allowed |
| Write the work folder, or the real `~/Library/Logs` | Operation not permitted |

Why the work folder could be read was not worked out, and **the same was not tried with the
app in `/Applications`**, where the runtime would have to be read from somewhere else: the
container is the place that is certain.

KotorPatcher finds `patch_config.toml` and `patches/` beside itself, not beside the game
(`src/KotorPatcher/src/core/patcher.cpp`), and it does not ask which program it is in. So:

- `loader.c`: a library to insert, which loads KotorPatcher only when the process is
  `KOTOR_Exe` (the launcher gets the same environment first);
- `make_runtime.py`: the package's staged `patch_config.toml` with every hook's address through
  the map, its original bytes read from the App Store's file and compared instruction by
  instruction, and its replacement bytes put right (the absolute target after a
  `jmp [rip+0]`, a rip-relative displacement, a relative branch that leaves the hook; a
  constant inside an instruction is left as it is);
- the modules compiled from the translated sources, with the build's own tools
  (`create-patch.py` run in the translated folder; `make_kmrp_patch.py --split` given the
  translated `--layout`, `--assets` and `--notes`).

**Run 1, Stray Bug Fixes alone.** All 16 hooks applied at their App Store addresses,
"patcher initialized", the game running at 30 s.

**Run 2, Stray Bug Fixes, the Widescreen Patch and KMRP** (no controller). 85 hooks applied,
"patcher initialized". KMRP's module, from the game's output: "the widescreen patch uses the
.gui layouts (1512x982)"; the set for 1512x982 made in the container's
`Library/Caches/KMRP/271e133cbc0d0cd5` with 867 files made by the module; 334 files of artwork
and 520 bundled linked; the artwork folder and the set registered with the game. The game was
running at 45 s at 7.6% CPU.

**Not seen: the screen.** No picture of either run exists. The devkit's screenshots are
written inside the container, a relay to print them to the output was written (`relay.c`) and
not run, and the session's safety check then refused further runs. So that the menus are
KMRP's, laid out right, is **inferred from the log, not observed**. Not run at all: the
controller patch (SDL reads pads through IOKit, and the sandbox has `device.usb` only, so a
Bluetooth pad may not be seen; GameController is the fallback), High FPS Fixes, a save, a
change of resolution.

## 5. What support would take

1. **The translation as build tools** (`macos/tools/`): the map made at build time from the two
   executables, the sources translated into the build folder, a second set of modules and a
   second staged hook list. The App Store's `KOTOR_Exe` cannot be shipped or fetched, so the
   build needs it beside Steam's, as it needs Steam's now.
2. **Another way to install and start**: KotorPatcher, the hook list and the modules in the
   game's container (KMRP's caches already go there by themselves, through `HOME`), and the
   game started through a launcher of KMRP's that sets `DYLD_INSERT_LIBRARIES` and runs
   `AppBundleExe`. Started from Launchpad or the Dock, the game would be the unpatched one. No
   administrator password, nothing of Apple's touched, and an update of the game cannot break
   the install, only outdate the addresses (the modules must then refuse, by the executable's
   hash).
3. **The settings**: `swkotor.ini` is in the container; the module can write there, the
   installer only with macOS's consent.
4. **KotOR Patch Manager** does not know this build (`GameDetector.cs` has Steam's only), and
   its way of installing is the one section 3 rules out; FTD's two patches would need a second
   hook table each, or be built by KMRP's translation as in the prototype.
5. **To verify before any of it is offered to players:** the screen; every group of sites that
   compares bytes; the controller in the sandbox; saves and settings in the container; the game
   in `/Applications` rather than a copy; an Intel Mac; macOS versions before 27.

## 6. Detection, as written

`kmrp-mac.sh`: `APPSTORE_EXE_SHA`, `APPSTORE_BUNDLE_ID`; `app_store_game` looks in
`/Applications`, `~/Applications` and through Spotlight by bundle id; `is_app_store_game` goes
by the bundle id or the receipt. With no Steam copy and an App Store one, `find_game` ends with
"KOTOR from the Mac App Store was found (...), and no Steam copy" and the reason; given the App
Store's bundle with `--game`, install refuses with the reason and status says "KOTOR_Exe: the
Mac App Store's game (not supported yet: ...)". The window (`main.m`) shows "Mac App Store
version 1.4.1 detected. KMRP supports the Steam version only so far." in step 2, and in step 1
"Only the Mac App Store version was found." Checked: the three functions against the two
bundles on this Mac (the App Store's found and recognised, Steam's not taken for it, the hash
matching). **Not built into a package; the window not looked at.**

## 7. What was built (2026-10-12, afternoon)

### 7.1 Where KMRP's files can be

Section 4 left open where the runtime could be read from with the game in `/Applications`.
Measured with a library inserted into the unmodified game there, reading and `dlopen`:

| Place | Read and load |
| --- | --- |
| a folder in `/Applications` beside the game | allowed |
| `~/Applications`, `/Users/Shared`, `/private/tmp`, the home folder, `~/Library/Application Support` | Operation not permitted |
| the folder the inserted library itself was in (the work folder) | allowed for the launcher; **not for `KOTOR_Exe`**, which read no script from there |
| the game's container | allowed |

So KMRP's files are in an app in the folder the game is in.

### 7.2 The parts

| Part | What |
| --- | --- |
| `macos/tools/appstore/translate.py`, `lookup.py` | the map between the two executables (section 2) |
| `rewrite_sources.py` | a source tree with every address translated; stops on one it cannot translate outside a comment |
| `make_runtime.py` | a staged `patch_config.toml` for the other executable: addresses, original bytes read from it, replacement bytes put right |
| `make_delta.py` | a module as the stretches in which it differs from Steam's |
| `macos/appstore/loader.c` | inserted into the game; loads KotorPatcher in `KOTOR_Exe` only, and only when that file has the SHA-256 the hooks were made for |
| `macos/appstore/fullscreen.m` | in the same library: makes the game's window cover the display when Aspyr's launcher is set to full screen (section 7.5) |
| `macos/appstore/launcher.c`, `Info.plist` | the app **KOTOR with KMRP**: sets `DYLD_INSERT_LIBRARIES` and `KMRP_PATCHER`, opens `~/Library/Logs/KMRP/appstore-game.log` for the game's output, and runs Aspyr's `AppBundleExe` in the game's folder |
| `macos/build.sh` | with the App Store's `KOTOR_Exe` at hand (`--appstore-exe`, default the game in `/Applications`): the map, the seven source trees, the five patches compiled by the tools that compile Steam's, the four hook lists, the deltas, SDL for the game's architecture, the loader and the launcher, into the package's `appstore/` |
| `macos/kmrp-mac.sh` | `--app-store`, or `--game` with that game, or no Steam copy: `do_install_app_store`, `do_uninstall_app_store`, `do_status_app_store`; state in `~/Library/Application Support/KMRP/macos-appstore` |
| `macos/installer-app/main.m` | the App Store's game is verified and patched like Steam's; its lines say what is different |

Build of that day: 1,175 addresses translated in the seven trees (424, 4, 219, 80, 1, 407,
40), none failed; the four hook lists with 0 problems, 138 hooks in the largest; the modules
as deltas of 0, 68,337, 1,052, 3,180 and 100 bytes (Stray Bug Fixes' module is the same file:
its addresses are all in its hook list). The package grew by 2.9 MB, 2.8 of it SDL.

### 7.3 Seen in the game

Through the installed app, `/Applications/KOTOR with KMRP.app`, the game in `/Applications`
unchanged, all five patches, 1512x982, screenshots taken by the devkit and copied out of the
container by `relay.c`:

| | |
| --- | --- |
| Hooks | 138 applied, "patcher initialized" |
| Main menu | KMRP's, the same picture as Steam's game at that size |
| Options, Graphics | KMRP's layouts |
| Screen Resolution | the display's sizes, 1024x640 to 1512x945 in view |
| A change to 1280x800 there | "resolution 1512x982 -> 1280x800", the set for it made and registered, "font metrics read again for 4 of 48 textures", "9 panels known, 32 extents set"; the Graphics screen laid out for 1280x800 with its text right |
| New Game | the class screen, KMRP's layout, the six portraits |
| Controller patch | "SDL3 3.4.16 loaded from .../KOTOR with KMRP.app/.../patches/kmrp-sdl3.dylib", "gamepad subsystem started", 20 bindings registered, its default settings written to the container |
| Opened with `open` (as Finder does) | Aspyr's launcher up with the loader mapped and `KMRP_PATCHER` set; PLAY not pressed in that run |

The game's `swkotor.ini` (in the container, 1,968 bytes, no `Width`) was copied out before the
change of size and put back after it, the same SHA-256.

**The controller's SDL.** The first run with the controller patch logged "SDL3: ...
kmrp-sdl3.dylib not loaded ... using GameController", and a second stopped with the log's last
line the one before that load and the game still up 50 s later. The module was loading the
copy of SDL it unpacks to its cache, which in this game is in the container, written by the
sandboxed game itself. With SDL beside the module in KMRP's app and looked for there first
(`backend_sdl.cpp`, `Load`), it loads. That macOS was asking about the unpacked file is the
likely reason for the stop and **was not seen**: no picture of that run exists, and the
maintainer reported library errors at the start of that session.

### 7.4 Not seen, not done

- A save loaded, play, a dialogue, a store, the map: the App Store copy has no save, and none
  was made.
- A controller connected (SDL reads pads through IOKit, and the sandbox has `device.usb`
  only: a Bluetooth pad may not be seen; GameController is the fallback), rumble, the HUD.
- High FPS Fixes' effect: its 26 hooks apply; no frame rate was compared.
- KMRP Installer's window with the App Store's game chosen: built, not looked at.
- The sites that compare bytes before they write (section 2, "Not checked"): the screens above
  are right at 1512x982 and 1280x800, which is those groups working for these screens, not a
  list of every group.
- An Intel Mac; macOS before 27; the game in another folder than `/Applications`; an account
  that cannot write `/Applications` (the installer refuses, with the reason).
- KotOR Patch Manager (section 5, item 4): unchanged, it does not know this build.
- `runpkg.sh` makes `/Applications/KMRP-probe` for its script (the sandboxed game reads nothing of the work folder); it was removed after the runs.

### 7.5 Full screen (1.5.1)

**The fault.** With "Full screen" chosen in Aspyr's launcher the App Store's game does not
cover the display. Measured on 2026-10-12 (macOS 27, the built-in 1512x982 display), the
window read with `CGWindowListCopyWindowInfo` and seen in a screenshot:

| Started | Window |
| --- | --- |
| the unmodified game, by its own `AppBundleExe` | 1024x796 with a title bar, centred (1024x768 inside it) |
| through **KOTOR with KMRP**, before this change | 1512x949 with a title bar, under the menu bar, the Dock over its foot; the game at 1512x982 drawn into the 1512x921 inside it |
| through **KOTOR with KMRP**, with this change | 1512x982 at 0,0, no title bar, no menu bar, no Dock |

The game's own setting was full screen each time: `Aspyr/Data.json` in the container had
`"ASL_DisplayFullScreen": true`. Why this build opens a window all the same was not found;
Steam's 1.4.0, with the same setting, covers the display.

**How the setting travels** (read from Steam's executable; the launcher's code is the App
Store's own): Aspyr's launcher keeps the choice under `DisplayFullScreen` in the
application's preferences, sets it to full screen when the key is missing (`0x10000eee3` in
`AppBundleExe`), and replaces itself with `KOTOR_Exe` (`execv`) with no argument about it. The
game then moves every key of those preferences into `Data.json` and deletes it from the
preferences (`0x10000cd23`), and renames `DisplayFullScreen` there to its own name
(`0x10002bb30`).

**Corrected the same day.** The first attempt (commit `4587552`) set `DisplayFullScreen`
from the loader inside Aspyr's launcher, "once", with a key `KMRPFullScreenSet` beside it.
It changed nothing: the launcher had that value already, and the game deleted the marker
with every other key at each start, so it was set again every time. It is removed.

**What KMRP does.** `macos/appstore/fullscreen.m`, part of `loader.dylib`, started in
`KOTOR_Exe` after the patcher is loaded:

1. Before `main`, it reads `DisplayFullScreen` from the preferences, where the launcher has
   just left it. "In a window" there: nothing more is done.
2. Twice a second on the main thread it looks at the game's window. One with a title bar, or
   not of the display's frame, is given no title bar (`NSWindowStyleMaskBorderless`) and the
   display's frame, and the application hides the menu bar and the Dock
   (`NSApplicationPresentationHideMenuBar`, `HideDock`), which macOS undoes while another
   app is in front. A window in macOS's own full screen (the green button) is left alone.
   After eight tries within five seconds of each other it stops.
3. It tells KMRP's module (`KMRP_WindowChanged` in `kmrp.dylib`, found among the loaded
   images), which asks Aspyr's window object for its mouse ratio again on the game's thread
   (`kmrp-assets/resolution.cpp`, `KeepSurface`). Without that the ratio stayed the one for
   the window with a title bar, 1.066 down: the pointer over Options lit Quit (measured with
   the devkit's pointer at 921,623).

**Seen:** the third row of the table; the game's log, "full screen: the window 1512x949
with a title bar now covers the display, 1512x982 (1)"; the main menu drawn over the whole
display; "mouse scale 1512x982 1.000,1.066 -> 1512x982 1.000,1.000" after it, and a click at
921,623, where Options is drawn, opening Options (it lit Quit before the ratio was asked for
again). **Not seen:** a change of resolution in the game with the window covered (the
window is expected to be sized by the game and covered again half a second later), a
second display, another app brought in front and back, "In a window" chosen in the
launcher, the unmodified proportions of a size that is not the display's shape (the picture
is stretched to the display, as a covered window does).

### 7.6 Addresses written as bytes (the crash at the first message box)

**The fault** (the maintainer, 2026-10-12: "when pressing load game in the kotor with kmrp
it crashes"). The App Store copy has no save, so Load Game opens the message box "You have
no saved games", and the game ended there: `EXC_BAD_ACCESS` at `0x1000efae0`, in a routine of
OpenSSL's that the game never calls (`0x1000efa00`; Steam's `0x1000f5000`). The unmodified
game shows the box.

**The cause.** FTD's widescreen patch writes small stubs into the padding before that routine
and 5-byte calls and jumps to them, as bytes: `uint8_t callFit[5] = { 0xe8, 0x2b, 0xe5, 0xde,
0xff }; writeMemBytes(0x100306a88, callFit, 5);`. `rewrite_sources.py` translated the literal
(`0x100301488` here) and not the four bytes, which are the distance from that site to the stub
in Steam's build. In this build the site is 0x5600 lower and the stub 0x5640 lower, so the
call landed 0x40 short of its stub, in the padding, and ran on into the routine after it. The
stub's own `mov rax, 0x10049dc36` was Steam's address too.

Found from the fault itself: the routine saves the stack pointer it was entered with
(`[rsp+0x110]`), and the word there was `0x10030148d`, the return address of
`CSWGuiMessageBox::FixMessageLabel`'s last call. (A handler for the fault in a test build of
the loader printed it; it is not in the package.)

| In FTD's `mac_widescreen.cpp` | Sites | What it is for |
| --- | --- | --- |
| `callFit`, `bridge` | `0x100306a88` to the stub at `0x1000f4fb8`, and the stub's return to `0x10049dc36` | the message box fitted to its text |
| `stub`, `hook` | `0x100244d7d` to `0x1000f4fd4` and back to `0x100244d84` | the dialogue's reply list |
| `callWorld`, `callParty`, `callPlayer` (twice each) | `0x1002b4fca`, `0x1002b541b`, `0x1002b54c2` to `0x1000f4f68` and `0x1000f4f78` | the area map's markers |
| `stretchFillStub`, `stretchFillHook` | `0x1004a2350` to `0x1000f4f90` and back to `0x1004a2376`, `0x1004a2355` | item icon borders (not in `.gui` mode) |

14 distances and addresses in all (Steam's addresses above), each 0x40 out in the App Store
build: with KMRP a message box, a dialogue and the area map each ended the game. None of the
three had been opened in this game (section 7.4).

**The repair** (`macos/tools/appstore/rewrite_sources.py`, `rewrite_byte_arrays`). Before the
literals, in every byte array that is written to a literal address: a call or jump (`e8`,
`e9`, `0f 8x`) whose target is in Steam's image gets the distance from the translated site to
the translated target, and eight bytes that are an address of the image get the translated
address. One that cannot be translated stops the build. An array with a call or jump and no
literal address to be written to is listed and left (one, KMRP's `kVanillaScrollBlock`, which
is compared, not written). The build prints the count: 14 in FTD's widescreen patch, 0 in
FTD's Stray Bug Fixes and in KMRP's own five trees, which work their distances out when they
run. The padding is long enough in both builds: 155 bytes of `nop` before the routine in
Steam's, 219 in the App Store's; the stubs end 15 bytes before it.

**Not covered:** an address inside bytes that are not a call, a jump or eight whole bytes (a
RIP-relative operand, `8b 05 ...`). None is in the sources today; the rewriter does not look
for them.

### 7.7 The audit of every address (2026-10-12, evening)

Asked for by the maintainer after 7.6 ("reinspect all the hooks ... dont assume steam version
is the same"), with a report from play: "camera doesnt work keyboard binds are wrong right
does left". The scripts and their output are in
`kmrp-macos/work/appstore-20261012/audit-20261012/` (outside the repository).

**How the two builds differ.** 1,294,360 instructions in Steam's `__text` and 1,290,183 in the
App Store's; 1,178,379 are paired by the map, 1,112 of them as "weak", of which 580 differ in
an operand the pairing keeps (a register, a stack slot, a field offset: 48 for 40 and 64 for
56 in Aspyr's own layer near `0x100037000`). About 116,000 instructions of each build have no
partner. `__bss` and `__common` are in the other order, as are `__TEXT,__const` and
`__cstring`. So the builds are not the same code at other addresses everywhere, and each
address KMRP uses was checked by itself.

**What was checked.** Every address in the sources of the seven trees and their hook tables
that is in Steam's image: 696, of which 576 stand outside comments.

| Check | Result |
| --- | --- |
| The 253 functions those addresses lie in, instruction by instruction against the App Store's | 229 the same in every operand. 20 more differ only in naming `0x1005106f8`, which the map does not translate and no source uses. 1 (`0x10001e36c`) calls a routine the map pairs wrongly (`0x1000a85f0`), which no source uses. 1 is the routine before the stubs' padding (three `loope` distances). 2 are SDL's (`0x1000c0240`, `0x1000be310`), 18 of 20 and 2 of 55 instructions without a partner: their starts are paired, their bodies are another SDL's |
| Each address against every paired instruction that names it (97,917 targets voted on) | none of KMRP's disagrees. In the whole map 106 code targets do, all below `0x1000c0000`, none used |
| The 11 data addresses no paired instruction names (9 constants and 2 vtables in FTD's widescreen patch, mapped as "between" or "content") | the 9 constants hold the same bytes, with the same 96 bytes around them; the vtables' first 48 entries are each other's translations but for 5 type-information pointers the map does not hold, which lie at the section's own distance |
| The 138 hooks in the game | all applied, none refused, nothing logged as not written |
| Addresses inside byte arrays | 14, repaired (7.6) |

**Not checked by this:** a field offset KMRP takes from Steam's code where the App Store's
routine that uses the field has no partner (the two SDL routines above are the only bodies of
that kind among the 253); what the 138 hooks do once applied, beyond the screens seen.

**The report from play.** With Game 22 loaded (the first save loaded in this game: the saves
were copied in from Steam's), D and then A held for one second each, the game's own
screenshots taken at fixed times, through **KOTOR with KMRP** and in the unmodified game: in
both the minimap's arrow turns clockwise for D and back for A. The key bindings in the App
Store game's `swkotor.ini` are the 62 of Steam's, entry for entry. The maintainer then said
what was meant: "the character that you play he moves very fast and everything in the world
moves very fast", and a two-finger swipe does not turn the camera. That is section 7.8; this
audit did not find it, because it compared sources and hooks' addresses and not the constants
inside the hooks' replacement bytes.

### 7.8 Addresses loaded as 64-bit constants in the hook list (work in progress)

**Measured** (2026-10-12 and 13, Game 22 loaded, V-Sync on, the devkit's frame times, five
seconds each):

| | Frames in 5 s, median frame |
| --- | --- |
| the unmodified game (V-Sync off, as installed) | about 1,200, 4 ms |
| with KMRP | 92, 56 ms, falling to 34, 148 ms after 40 s more |
| with KMRP less FTD's Stray Bug Fixes | 603, 7.3 ms |
| with KMRP less four of that patch's hooks (`0x1001d0663`, `0x1001fa2bf`, `0x1001e00cd`, `0x1001e1627` in Steam's addresses) | 606, 7.4 ms |

**The cause, read from the hook list.** `make_runtime.py` put right what moves in a hook's
replacement bytes when it is the target after `jmp [rip+0]`, a rip-relative operand or a
relative branch. An address loaded as a 64-bit constant (`48 b8`, `movabs`) was left as
Steam's. Three hooks have one:

| Patch, hook (Steam's address) | Loads | Left as Steam's, in the App Store's game |
| --- | --- | --- |
| Stray Bug Fixes `0x1001fa2bf`, the clamp on the highest texture id | `0x100635ba8`, the variable | another variable is read: the loop that clears the texture buckets runs over a count that grows. Taken to be the slowdown: it is among the four hooks above; not yet separated from the other three |
| Stray Bug Fixes `0x1001d0663`, the guard on a texture id of 5,000 or more | `0x1001d067b`, where to return | a return into other code, only for such an id |
| High FPS Fixes `0x1001ae688` | `0x1005ca818`, the frame's length in seconds | another variable is read as the frame's length. Taken to be "everything moves very fast"; not measured |

**The repair, written and not yet built or tested:** `make_runtime.py` (`rebase`) translates a
64-bit immediate that is an address of Steam's image and stops the build on one it cannot.
A build with it was started on 2026-10-13 and stopped before it finished.

**Corrected on the way.** A first conclusion blamed KMRP's surface check in the GUI's frame
(`KeepSurface`): runs with it left out were fast. In those runs the scripted click on Load
had missed (the mouse ratio was not refreshed with the frame hook off), so they measured the
menu. With each run checked to be in the game, the frame hook makes no difference. A change
to `KeepSurface` made on that conclusion was taken out again.

**Open:** the build and its measurement; walking and turning speed against the unmodified
game with the repair; the two-finger swipe (not looked at; it may be the frame rate);
whether V-Sync off, as the App Store's game is installed, needs anything from KMRP (the
unmodified game ran at about 240 frames a second in play). For these tests V-Sync was
switched on in the maintainer's copy of the game and left on.
