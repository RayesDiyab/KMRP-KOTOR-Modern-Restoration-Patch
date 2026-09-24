# Issue #14: the white flash, caught on video and pinned to one transition

**Status: resolved, 2026-09-19 — read [Part 4](#part-4-the-driver-shows-unfinished-frames-and-the-engines-long-frames-expose-it)
first.** NVIDIA's "Prefer layered on DXGI Swapchain" present path shows frames
the game has not finished; KMRP's installer now keeps KOTOR off it, and a menu
fix removes the flash for players who choose it anyway. Parts 1–3 are the
investigation as it happened, with their wrong turns marked in Part 4.

Part 1, as first written: this is the first time the flash has been captured
rather than described. Recorded 2026-09-15 by driving the game with synthetic
input while `ffmpeg` recorded the screen, because the machine was unattended.

Supersedes nothing. It sits alongside
[`texture-residency.md`](../texture-residency.md), which describes the
mechanism, and [`white-flash-analysis.md`](white-flash-analysis.md), which
records the static analysis and the two models this run now rules out.

> **Read Part 2 below before acting on Part 1.** Part 1 leaves "what draws
> `RGB(138, 146, 141)`" open and looks for it among textures. Part 2 answers it
> — it is the area's `SunFogColor` and the frame is a bare `glClear` — and
> retires the texture hunt entirely.

## What the flash is

**One frame. The whole screen. One flat colour.**

| property | measured |
| --- | --- |
| duration | exactly one frame at 60 Hz — 16.7 ms |
| colour | `RGB(138, 146, 141)` |
| coverage | 99.98% of the frame is that single value |
| variation between occurrences | none — every flash in every run has mean 141.66 to two decimals |
| where it lands | the frame immediately before the Equipment screen's first drawn frame |

The 0.02% that is not the flat colour is chroma ringing from the h.264 encode,
not content.

## The trigger, isolated

The last two runs separate "leaving the Options screen" from "entering the
Equipment screen". They are the same length, the same click rate, the same save,
minutes apart.

| run | alternating between | screen switches | duration | flashes |
| --- | --- | ---: | ---: | ---: |
| A | Options ↔ Journal | 20 | 36 s | **0** |
| B | Character ↔ Equipment | 20 | 36 s | **8** |

Every flash in run B has the Equipment screen as the frame *after* it. So the
trigger is **entering the Equipment screen**, not leaving any particular one,
and it fires on 8 of 10 consecutive entries — 80%.

## Everything recorded

Protocol: launch, load a save, open a menu, click through screens on a fixed
timer while recording. Detector: per-frame mean over RGB; a flash is a frame at
least 25 above **both** its neighbours, which no ordinary screen change can be
because a screen change persists into the next frame.

| run | save | what was driven | events | duration | flashes |
| --- | --- | --- | ---: | ---: | ---: |
| cap1 | Manaan quicksave | inventory filter rotation | 26 clicks | 45 s | **0** |
| cap2 | Manaan quicksave | held one filter view still | — | 28 s | **0** |
| cap3 | Manaan quicksave | tab strip | 16 switches | 42 s | 2 |
| cap4 | Manaan quicksave | tab strip | 56 switches | 95 s | 10 |
| cap5 | Manaan quicksave | tab strip, **gdigrab** | 24 switches | 40 s | ≥3 |
| cap6 | Tatooine, Game 177 | tab strip | 24 switches | 45 s | **0** |
| cap7 | Tatooine, Game 177 | tab strip | 56 switches | 95 s | **0** |
| cap8 | Manaan, fresh session | tab strip | 56 switches | 95 s | 6 |
| capA | Manaan, fresh session | Options ↔ Journal | 20 switches | 36 s | **0** |
| capB | Manaan, fresh session | Character ↔ Equipment | 20 switches | 36 s | 8 |

cap4 and cap8 are the identical 95-second protocol on the same save, one in a
25-minute-old session and one in a 5-minute-old one: 10 flashes and 6. cap7 is
that same protocol on a different save: none at all.

## What this rules out

**It is not the inventory filter rotation.** 26 rotations produced zero flashes,
and holding one view still for 20 seconds produced zero. The recollection that
it happens "when cycling X in the inventory" points at the *screen* switch that
surrounds that cycling, not at the filter.

**It is not the texture-bucket overrun.** The instrumentation reports
`maxTexID` against the 5000-entry bucket arrays every frame. It peaked at
**471** in the Manaan session and **296** on Tatooine — the arrays were never
close to overflowing, and the flash happened anyway. (The KPM safety patch was
installed for all of these runs, so this also says the patch is not what
suppresses it, because it is not suppressed.)

**It is not a first-use texture build.** The flash repeats on 8 of 10
*consecutive* entries into the same screen inside 36 seconds. A first-build cost
is paid once.

**It is not a capture artifact.** Two independent capture paths were used —
DXGI Desktop Duplication (`ddagrab`) and GDI (`gdigrab`) — and both show it. In
the GDI capture the grab is torn, so the flash frame is 84–90% the flat colour
with a partly drawn GUI in the top strip; the dominant colour there is
`RGB(138, 146, 141)`, the same value.

## What is still open

**What draws `RGB(138, 146, 141)`.** It is not the average colour, nor the
smallest stored mipmap, of any of the **1,570** textures in
`swpc_tex_gui.erf` — the nearest is `Gui_Clouds_1` at a distance of 7.6, and
that texture is not drawn on this screen. Nor of any of the **758** `.tga`
files KMRP installs into `Override` — nearest 16.1. So the "a texture collapsed
to its 1×1 mip" reading is not supported by the data, and the "unbound texture,
so the quad takes vertex colour 1,1,1" reading predicts pure white, which this
is not.

**Why it is save-dependent.** The same protocol, the same build, minutes apart:
Manaan flashes on nearly every Equipment entry, Tatooine never does in 56
switches. Something about that save or that module decides it. Party
composition, equipped items and the size of the inventory are the obvious
candidates and none of them has been tested.

The measurement that would settle the first question is a graphics-level trace
of the Equipment screen's first frame — what is bound and what is drawn when the
screen is constructed. That is a different kind of session from this one.

## An unrelated defect found while looking

On this save the Inventory's **Utility Items** and **New Items** filter views
draw four item icons — the four Crossguard Emitter rows — as a solid white
block. Measured: 12,104 white pixels in the icon column against a resting 19,
**held for 20 seconds** with no input, so it never resolves. That is a missing
or failing icon resource, not a timing flash, and it has nothing to do with the
one-frame event above. Worth its own issue.

## One crash, not reproduced

Loading a save **from inside a running game** segfaulted once (the process
exited 139, no dump, no crash log). Loading the same save from the main menu
worked on the next attempt, and 5 further minutes of play on it were clean. One
occurrence, on a path vanilla KOTOR is not reliable on either; recorded here so
it is not lost, and **not attributed to anything**.

## How it was captured

Unattended, so everything was scripted.

- `ffmpeg 9.0.1` via `ddagrab` (DXGI Desktop Duplication) at 60 fps, the
  display's own refresh rate, downscaled to 1720×720 and encoded
  `libx264 -preset ultrafast -crf 16`. 2,700 frames per 45 s, no drops.
- Input by `SendInput` from a small Python `ctypes` helper. A PowerShell version
  of the same thing is blocked by Defender's AMSI as a keylogger signature;
  Python is not scanned.
- Screen 3440×1440 at 60 Hz, game `FullScreen=1`, `V-Sync=1`, so one presented
  frame is one captured frame.
- Detectors: whole-frame mean for the full-screen flash, and a block-wise
  version (the frame divided into 10 px blocks, each compared against itself
  three frames either side) for local flashes, because an 84×84 icon turning
  white moves the whole-frame mean by only 0.27.

Scripts and the captures are in the session scratchpad, not the repository —
they are 90 MB of video. The frames that matter are `white-flash-equip.png`
(before / flash / after) and `white-flash-slowmo.mp4`.

---

# Part 2: what the flash actually is

The first part of this note ended with "what draws `RGB(138, 146, 141)`" open,
and guessed at textures. That was the wrong family of answer.

## It is the area's fog colour, and the frame is a bare `glClear`

Every fog and ambient colour field in the game was read — **819 of them across
every module** — and ranked against the measured flash. Then the model was
tested by **predicting a different area's flash colour before capturing it**.

| area | field | value in the `.are` | measured flash |
| --- | --- | --- | --- |
| Ahto City `manm26aa` | `SunFogColor` | RGB(140, 147, 143) | RGB(138, 146, 141), 99.98% of screen, 13x |
| Sith Base `manm27aa` | `SunFogColor` | RGB(197, 215, 252) | RGB(194, 214, 250), 99.42% of screen, 4x |

Both off by the same small negative bias — (-2,-1,-2) and (-3,-1,-2) — which is
the h.264 encode of a flat field, not a mismatch. The nearest of the other 817
candidates was **nine times further away** than the Ahto match.

`SunFogOn` is **0** on both modules, so the renderer uses the field as its clear
colour whether or not fog is enabled.

**So the flash is one presented frame containing nothing but the frame's
`glClear`.** It reads as "white" on Manaan only because Manaan's fog is a pale
grey-green.

## The frame loop, and why that is all it can be

There are exactly **two** `SwapBuffers` call sites in the image:

| site | function |
| --- | --- |
| `0x004048C1` | `WinMain+0x6d1` — the real frame loop |
| `0x00401CC2` | `UpdateScreen+0xb2` — the "keep the window alive during a long operation" helper |

`WinMain` is `glClear(COLOR|DEPTH|STENCIL)` at `0x00404681` →
`CClientExoApp::MainLoop` → `SwapBuffers`. So a frame that presents only the
clear is an iteration where **`MainLoop` rendered nothing**.

`CClientExoAppInternal::MainLoop` (`0x00602EB0`) calls `CSWGuiManager::Update`
(`+0xdeb`) and `CSWGuiManager::Draw` (`+0xe71`), and **both are unconditional
straight-line code**. Disassembling the whole function, there are exactly three
ways out before the render, all inside one block gated on a client-state test:

| exit | condition |
| --- | --- |
| `0x0060332E` `je 0x0060410C` | `[esi+0x250] == 0` |
| `0x0060333A` `je 0x0060410C` | `[esi+0x254] == 0` |
| `0x00603354` `ret` | fall-through of the same block |

## Ruled out, each with a measurement

| candidate | how it died |
| --- | --- |
| the screens are built on demand | `createAllGUIs` (`0x007A2370`) is **already 1** in both the clean and installed images, and nothing in the image ever writes it — `UpdateCreatedInGameGUI` is a no-op |
| an extra `UpdateScreen` swap knocks the buffer chain out of phase | breakpoint on `UpdateScreen`'s swap: **0 hits** across a full protocol run |
| frame pacing / the missing frame cap | `lockFrameRate` (`0x007A3C64`, Lane's name) ships as 0.0 = disabled. Set to 60.0 through the hook table: **8 flashes, unchanged** |
| K1DC's screen effects | `framebuffer = off`: **9 flashes, unchanged** |
| K1DC doing extra work on that frame | `log = debug` for a whole 9-flash run: **not one line logged** |
| the GPU presenting a frame before its draws finished | every one of 13+ flash frames is 99.98% uniform. A late GPU would show partly-drawn frames sometimes; none ever did |
| the `MainLoop` early-exit block | breakpoint at its entry (`0x006032D8`), armed across a full protocol run: **0 hits** |

## The instrument problem, stated plainly

**The bug does not reproduce under a debugger.** Two separate sessions, three
protocol runs, zero flashes — including a run whose only breakpoint had a hit
count of 0 and therefore cost nothing. Attaching at all is enough to suppress
it.

That is not a failure to find it, it is a finding: this bug lives in the
engine's normal unthrottled timing, and **x64dbg cannot observe it**. The next
instrument has to be in-process and free — counters in KMRP's own module, which
already hooks `CSWGuiManager::Update` once per frame, logging the frames where
`CSWGuiManager::Draw` submitted nothing.

## Still open

Why an iteration renders nothing, given that the only three early exits never
fire. Either the render happens and is discarded, or there is a fourth path out
that static reading of `MainLoop` did not reveal.

---

# Part 3: the frame is drawn, and then lost

Part 2 ended with "why does an iteration render nothing". The premise was
wrong: **it renders.** Measured from inside the process, because the bug does
not survive a debugger.

## The probes

Two detours in `kmrp-controller.module`, both at sites verified byte-identical
in the clean and installed images and both position independent:

| site | hook | what it records |
| --- | --- | --- |
| `0x0040CC50` `CSWGuiManager::Draw` | `NativeGuiManagerDrawK1` | that the draw ran, and how many panels carried the draw bit |
| `0x004048C1` `WinMain+0x6d1` | `NativeFrameSwapK1` | one line per presented frame |

Plus an import-slot hook on `0x0073D21C` — the single slot all 22 `glClear`
call sites go through — which numbers every `GL_COLOR_BUFFER_BIT` clear so it
can be ordered against the draw.

They write to `kmrp-frame-probe.log` beside the module. The module's existing
diagnostic line was no use here: it only reaches disk from the joystick init
and movement hooks, so with no pad enumerated it never writes at all.

## The result

One protocol run, 10,801 presented frames, **10 flashes captured on video in
the same span**:

```
alive swaps=10801 nodraw=0 drewnothing=0 draws=10902 panels=3 clears=34028 late=0
```

| counter | meaning | value |
| --- | --- | ---: |
| `nodraw` | frames presented with no `CSWGuiManager::Draw` at all | **0** |
| `drewnothing` | frames whose draw had no drawable panel | **0** |
| `late` | frames where a colour clear landed AFTER the draw | **0** |
| `clears` | colour clears seen, ~3 per frame in gameplay | 34,028 |

The `clears` figure matters: it is what proves the clear probe was live, so
`late=0` is a real negative and not a silent probe. (`draws` runs a constant
101 ahead of `swaps` — startup `UpdateScreen` calls — and tracks it exactly
after that, so it is one draw per presented frame.)

## What is now eliminated, from inside

| model | verdict |
| --- | --- |
| the loop skipped the render | dead — `nodraw=0`, `drewnothing=0` |
| the GPU presented work it had not finished | dead — `glFinish` before every swap: **9 flashes, unchanged** |
| a second clear wiped the drawn frame | dead — `late=0`, with the probe proven live |

So: the GUI is drawn for the flashed frame, nothing wipes it, the GPU has
finished, and the screen still shows the bare clear.

## What that leaves

The drawn frame went somewhere that is not the presented buffer. That fits
K1DC rendering the frame into an offscreen target and blitting it to the back
buffer, with the blit missed for one frame — leaving exactly the default
framebuffer's clear, which is the area `SunFogColor`. It also fits every
earlier measurement:

- flash colour is the clear colour, always
- `decline = on` removes it (8/10 → 0/10) while `framebuffer = off` does not
- K1DC logs nothing on those frames, because a missing blit is not an action
- the residual ~1/10 with K1DC declined is the *other*, milder artifact: the
  backdrop drawn with an empty panel interior

**Not yet proven.** The measurement that would settle it is forcing the clear
colour to black while an in-game menu is up: if the flash turns black, what is
on screen is definitively the default framebuffer's clear showing through.

---

# Part 4: the driver shows unfinished frames, and the engine's long frames expose it

Part 3 ended on an unproven K1DC-blit model and a test to settle it. The test was
run and the model died; what replaced it is below, measured on
2026-09-18/19 on one machine: NVIDIA GeForce RTX 3080, driver 32.0.16.1656,
3440×1440 at 60 Hz, `FullScreen=1`, `V-Sync=1`, gold
`9DD81A75F4888FD67242B682BEE0AB4392EA8923CDF4A020CA3EDD2464C05E0A` (the
executable on disk is not modified by anything here; every change is a hook in
KMRP's table or an installer step). Addresses are `VA`.

## The answer

**NVIDIA's "Vulkan/OpenGL present method: Prefer layered on DXGI Swapchain"
puts frames on screen that the game has not finished drawing.** The engine's
frames are ordinary — clear, draw, `SwapBuffers` — but whenever one stalls
partway, that path shows its current state. What the player sees depends on
where the stall falls:

| stall | what is on screen | seen as |
| --- | --- | --- |
| after `WinMain`'s clear, before the menu draws (Show New Items, a tab switch: 15–65 ms) | the bare clear, the area's `SunFogColor` | **the white flash** |
| inside `CSWGuiManager::Draw`, after `DrawPCBG` (the Utility and Equipable filters) | the menu backdrop alone, no tabs or panels | the menu "refreshing" |
| inside the world render on the frame a menu closes | part of the world, the rest black with 8×8 blocks at the edge | a half-drawn frame, characters missing |

On the driver's native path none of the three appears, with or without any
KMRP code. KMRP did not cause the leak. Its frames stall long enough to expose
it — 15–65 ms here — and the issue's own note that stock KOTOR does not flash
is consistent with stock stalling for less, but stock's frame times were **not
measured**. All five backdrop-only frames captured were on a switch into the
Utility or Equipable filter, the two lists holding the items whose icons are
missing from the install; that the icon lookups are the stall is likely and
**not measured**.

## The black clear settled Part 3

Forcing `glClearColor` to black immediately before `WinMain`'s clear (a
diagnostic switch in the probe build) turned the flash **black**. So what is on
screen is the default framebuffer's own clear, not a missed K1DC blit.

## Where the time goes, from inside the process

A flight recorder in the probe build kept the last 256 frames with QPC
timings and dumped them on a key press (Scroll Lock), so a person watching
could mark a flash without a debugger (which suppresses the bug, Part 2).

| measurement | value |
| --- | --- |
| menu frames, clear → first GUI draw | median 0.4 ms (1,026 frames) |
| the frame that opens the inventory | 66.5, 66.8 and 63.4 ms clear → draw |
| person-marked flashes | each followed a clear → draw gap of about 30 ms (4 of 4) |
| gameplay frames, clear → `Scene::Render` | median 0.8 ms; `Scene::Render` before the GUI update in **631 of 631** |
| menu frames that call `Scene::Render` before the GUI update | **0 of 1,302**; the Character screen calls it after, for its model (117 of 117) |
| `UpdateScreen` swaps inside a recorded frame | **0 of 3,758** — no second present |
| `glDrawBuffer` asking for anything but `GL_BACK` | 3,200 logged, **all with a framebuffer object bound** (4 or 7) from `RenderOverlayConvolution` (`0x0042C753`) and `GLRender::RenderFrameToTextureATI` (`0x004335B1`) — rejected by GL, so the engine never draws to the front buffer |

`Scene::Render` is `0x004512D0` (virtual, slot `+0x18` of `Scene_vtable`
`0x00741708`); nothing calls it directly. Its own three `glClear` calls
(`0x004516C1`, `0x00451740`, `0x00451871`) are stencil-only (`0x400`).
`CSWGuiManager::Update` (`0x0040CE70`) draws nothing: it updates the shown panels
and removes the ones marked to go (`(flags >> 9) & 3`), and so does the tail of
`CSWGuiManager::Draw`.

## Which present path the driver took

`nvwgf2um.dll` (NVIDIA's Direct3D driver) and `d3d11.dll` loaded into this
OpenGL game mean the driver is presenting through a DXGI swap chain. Read from
the running process, in-game with a save loaded:

| NVIDIA setting for swkotor.exe | vanilla (1024×768, no K1DC) | KMRP (3440×1440, K1DC) |
| --- | --- | --- |
| global **Prefer layered on DXGI Swapchain** (this machine's global) | layered | layered |
| **Auto** (NVIDIA's default, `OGL_CPL_PREFER_DXPRESENT_DEFAULT`) | native | native |
| **Prefer native** | — | native |

At the main menu, before a save is loaded, vanilla on the layered global had
not loaded the DXGI modules yet; the reading has to be taken in-game. The
display-mode change vanilla makes (1024×768 on a 3440×1440 desktop) did not keep
it off the layered path, so resolution is not the trigger. The
`DISABLEDWM` compatibility shim present on every KOTOR copy on this machine is
not the trigger either: removed, the glitches continued (6 in the next run).

## The matrix

Two-minute captures at 60 fps (`ddagrab`), the player cycling the four
inventory filters with X, switching tabs and closing the menu; a flash is a
frame under ⅕ of the median spatial variance, an unfinished frame is one that
differs from both neighbours while they agree.

| present method | KMRP menu fix | flat frames | unfinished frames | notes |
| --- | --- | ---: | ---: | --- |
| layered (global) | off | 7 of 8 tab entries flashed | — | 09-18 A/B, the experiment build |
| layered (global) | on | 0 of 8 | — | same run |
| layered (global) | on | 0 | 2 | backdrop-only on Equipable→Utility; half-drawn close |
| layered, `DISABLEDWM` removed | on | 0 | 6 | 4 backdrop-only, 2 half-drawn closes |
| **Prefer native** | on | 0 | 0 | engine frame time 16 ms (60 fps) |
| **Prefer native** | **off** | 0 | 0 | fix confirmed off in the live process, below |

"Fix off" was checked three ways: the live bytes at `0x0040467C` and
`0x004512D0` read back as the game's own instructions while `0x0040CE70` read back
as the runtime's `E9` jump; the module's `fcl` counters stayed `0/0/0` for all
236 log lines of that session; and the config had the two hooks removed before
launch.

On the native path the capture saw at most 33 new frames a second against
60 on the layered path, so a single-frame glitch there would be caught about
half the time; the player watching saw none either, and the engine's own delta
(`dt` in the diagnostic line) stayed at 16 ms, so the game itself ran at 60.

## What ships

**1. The installer sets the present method, only where it is needed.**
`NvidiaPresentOperations` in `src/patcher/KmrpPatcher.cs` asks NvAPI which
profile the driver applies to the installed `swkotor.exe` (by full path) and
what it resolves `OGL_CPL_PREFER_DXPRESENT` (`0x20D690F8`) to. Only when the game
would **inherit** Prefer layered (`1`) does it set **Prefer native** (`0`) in
the game's own profile — normally NVIDIA's predefined "Star Wars: Knights Of The
Old Republic" — and record that in `KMRP_NVIDIA.manifest`. Auto, native, and a
value someone set in the game's profile are left alone. Restore removes the
value only while it is still KMRP's. See
[`docs/nvidia-present-method.md`](../../docs/nvidia-present-method.md).

**2. The menu frame skips its colour clear.** For players who choose the
layered path deliberately (RTX HDR needs it), the white flash is still the most
visible of the three. Two detours:

| VA | hook | stolen bytes | what it does |
| --- | --- | --- | --- |
| `0x0040467C` | `NativeFrameClearK1`, `skip_original_bytes` | `68 00 45 00 00 FF 15 1C D2 73 00` (`push 0x4500; call [glClear]`) | issues the clear itself, without `GL_COLOR_BUFFER_BIT` while the tab strip was up at the last GUI update |
| `0x004512D0` | `NativeSceneRenderK1` | `83 EC 10 53 55 56 57` | if that colour clear is still owed, does it before the world draws |

The GUI update hook at `0x0040CE70` decides "up" (the tab-strip panel, vtable
`0x00750148`, has the shown bit `0x04` and neither leaving bit `0x600`) and
settles an owed clear there if the menu has gone and no world was drawn. The
menu art covers every pixel on all eight tabs (compared screen by screen with
and without the switch), and on the frame a menu closes the world is drawn
after a colour clear exactly as before. The clear colour at the late point
equalled the frame start's in **54 of 54** closes, measured by tracking
`glClearColor` through its import slot; that tracking was then removed as
unnecessary. The counters are `fcl=dropped/deferred` in the diagnostic line:
one session read `fcl=2214/6` for six closes.

This is a mitigation for the layered path, not a repair of an engine fault. It
does nothing for the backdrop-only and half-drawn frames; only the native path
removes those.

## Corrections to Parts 2 and 3

- Part 2, "the GPU presenting a frame before its draws finished — **none ever
  did**": wrong. They do on the layered path; the backdrop-only and half-drawn
  frames above are exactly that. Part 2's flash frames were uniform because the
  stall it measured sits before any drawing.
- Part 2, "why an iteration renders nothing": it never did not render. The
  rendered frame reached the screen; the bare clear reached it earlier.
- Part 3, "What that leaves" (K1DC rendering offscreen and missing a blit):
  wrong, killed by the black-clear test.
- Part 3 recorded K1DC `decline = on` taking the flash from 8 in 10 to 0 in 10.
  That was not re-measured here and the model above does not explain it; whether
  the declined build still takes the layered path in-game is **untested**.

## Not changed

- The engine's frame loop, the clear on any frame without the menu up, and every
  gameplay frame.
- NVIDIA's global profile, and any profile value set for the game on purpose.
- AMD and Intel: no equivalent path was seen or tested.
- The missing inventory icons in the Utility and Equipable filters
  (`iw_lghtsbr_011`–`013`, `iw_sbrcrstl_022`–`024`, `029`), shown as white
  squares and the likely cause of those filters' stalls — a content fix, still
  open.

## Verifying by hand

1. NVIDIA Control Panel → Manage 3D settings → Program Settings → swkotor.exe →
   Vulkan/OpenGL present method. With the global on Prefer layered and the game
   on "Use global setting", a KMRP install should change it to Prefer native.
2. In-game, list the modules of `swkotor.exe` (Process Explorer, or
   `(Get-Process swkotor).Modules`): `nvwgf2um.dll` present means the layered
   path.
3. `testing/regression/Test-NvidiaPresentMethod.ps1 -GameExe <path>` prints what
   the driver applies to the game and runs the install/restore cycle on a
   throwaway executable.
4. For the menu fix, the diagnostic line's `fcl` counters: the first grows by one
   per menu frame, the second by one per menu close.
