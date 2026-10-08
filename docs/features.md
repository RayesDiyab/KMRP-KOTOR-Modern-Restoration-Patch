# What KMRP changes

Everything KMRP does to *Star Wars: Knights of the Old Republic* compared with the
game as it comes from Steam or GOG, in plain words. Nothing here needs technical
knowledge. The same list with how each item is done and where it lives in the code is
in [features-technical.md](features-technical.md).

KMRP changes how the game looks, fits and controls. It does not change the story,
the quests, the balance or any of the game's content, apart from one optional fix to
misplaced map notes.

## At a glance

- The game runs at your display's own resolution, including ultrawide and 4K, with
  menus and text made for that size.
- Text, lists, icons, popups, the map and the movies are all the right size and in
  the right place.
- Several crashes and glitches of the original game are fixed.
- A controller works everywhere, with the right button pictures for your pad.
- Higher-quality portraits, icons and menu art.
- One installer, one click, and one click to undo everything.

## Resolution and screen

| In the original game | With KMRP |
| --- | --- |
| Menus are made for 4:3 screens and a handful of old resolutions. Widescreen needs several separate tools and mods. | The game starts at your display's current resolution. Nothing to choose, nothing else to install. |
| The resolution list is short and ignores modern displays. | The game's Screen Resolution setting lists every resolution your display supports, and you can switch between them in the game. |
| Moving the PC to another screen means patching again. | Connect another display, a 4K television for example, and its resolutions appear in the list on their own. If the new display cannot show the resolution you last used, the game starts at that display's own resolution. |
| Ultrawide and unusual sizes show stretched or misplaced menus. | Every shape from 4:3 to 32:9 is covered, from 800x600 up to 8K and beyond. 66 common resolutions have menus built for them, and any other size gets menus fitted to it automatically. |
| Windows display scaling (125%, 150% and so on) can zoom the game a second time. | The game is shown at its true size whatever Windows scaling is set to. |
| On a PC with more than one monitor, the mouse can leave the game. | The mouse stays inside the game while it is in fullscreen. |

## Text and menus

| In the original game | With KMRP |
| --- | --- |
| Text stays tiny at high resolutions. | Text grows with the resolution and is drawn sharp for it, not enlarged from a small picture. |
| Rows and icons in lists stay tiny too. | Inventory, shop, equipment, quest and other lists have rows and icons sized to match the text, with each row sitting neatly in its box. |
| Item stack numbers disappear when icons are enlarged. | Stack numbers stay on their icons. |
| Long descriptions run under the scrollbar, or past the edge of their box. | Descriptions stay inside their box and clear of the scrollbar. |
| List rows grow a little taller every time a list is refreshed. | Rows keep their size. |
| Message boxes, tutorial boxes and confirmation boxes cut their text off. | Boxes grow to fit what they say. |
| Short on-screen notices are oversized at 4K, and the Feedback options sit on the scrollbar. | Both are sized and placed correctly. |
| During conversations the black bars are the wrong height on wide screens. | The bars fit the screen. |

## Map

| In the original game | With KMRP |
| --- | --- |
| The area map does not fill its frame on wide screens. | The map fills its frame. |
| A strip down the side of the map is never covered by fog, showing places you have not been. | Fog covers the whole map. |
| Clicking a map marker misses: the clickable spot is beside the marker you see. | You click the marker you see. |
| Markers stay tiny at high resolutions. | Markers scale with the screen. |
| The small map in the corner of the screen is not centred on your character. | It follows your character at every resolution. |
| About 250 map notes sit in the wrong place, a mistake from 2003. | The notes are where they belong. This one is optional (on by default) and is the work of Derslok. |

## Movies

| In the original game | With KMRP |
| --- | --- |
| Starting a movie switches the monitor to 640x480; the game can flicker, minimise or lose focus. | Movies play at the resolution the game is running at. No switch, no flicker. |
| On wide screens movies are zoomed in and cropped. | The whole picture is shown, with black bars where the movie is narrower than the screen. |

## Stability

| In the original game | With KMRP |
| --- | --- |
| Opening the inventory can crash the game when an item has a long description. | Fixed. |
| The game can run out of memory in long sessions or with large texture mods. | On the GOG and disc versions the game may use twice as much memory. (Steam's version cannot take this change; the other fixes apply to it as well.) |
| Rare crashes tied to textures, grass and saving. | Fixed, using the fixes from KOTOR Patch Manager. |
| On many modern graphics cards lighting, fog, reflections, soft shadows and grass are broken or have to be switched off. | They work. This part is optional (on by default) and is Synchro's K1 Modern Driver Compatibility. |
| On some NVIDIA setups the menus flash white or show half-drawn pictures. | The installer sets the one driver option that prevents it, for this game only, and removes it again when you undo KMRP. |

## Above 60 frames per second

The original game misbehaves above 60 frames per second: timing and animations
run wrong. With **High FPS Fix** on, KMRP also installs D3M0's High FPS Fixes,
which repairs these. The installer switches it on by itself when your display
runs above 60 Hz, and leaves it off on a 60 Hz display; you can change it in the
options either way. It is another author's work, included unchanged.

The frame rate itself is chosen in the game, in the same list as the resolution:
Options, Graphics, Screen Resolution shows each resolution once for every refresh
rate your display has, for example "3440 x 1440 @ 120 Hz". The original game hides
the rates above 85 Hz; with High FPS Fix they are all there and the game starts at
the highest. Without it the game is held at 60.

## Sharper artwork

- Party portraits in high quality (by MadDerp).
- Item icons in high quality (by JackInTheBox). Optional, on by default: switched
  off, the game keeps its own icons.
- Sharper menu art, and feat, power and skill icons that scale with the screen.

## Controller support

The original PC game has no real controller support. With KMRP a pad works in the
game and in every menu. It is installed by default and can be left out.

**Pads.** Xbox pads, PlayStation pads, Switch pads and the Steam Deck. The button
pictures on screen match the pad you are holding, and they disappear as soon as you
use the mouse or keyboard. You can switch between pad and mouse at any time.

**Playing.**

- Left stick moves your character, as slowly or quickly as you push it. Right stick
  turns the camera.
- A does the obvious thing with your target: talk, open, use, attack.
- The shoulder buttons pick the previous or next target. The left trigger switches
  party member, the right trigger pauses.
- The D-pad works the action bar: pick an action, press A to use it.
- In a fight, X disengages and Y removes the last queued action.
- Start opens the map, Back asks about Solo Mode, and clicking the right stick
  switches free look.

**Menus.**

- The D-pad or left stick moves through every screen; A selects, B goes back.
- The triggers switch between the menu tabs, and the right stick scrolls long text.
- In conversations you pick a reply with the D-pad and confirm with A.
- Character creation, level-up, shops, containers, saving and loading, the options
  and Pazaak's wager are all usable without touching the mouse.
- A or Start skips a movie.

**Controller Layout screen.** Options, Gameplay has a new screen showing what every
button does, with the pictures of your pad.

**Rumble.** Three settings: off, the original Xbox version's rumble, or an enhanced
one with lightsabers igniting and clashing, blaster recoil, hits taken, explosions
and Force powers. Strength can be adjusted.

**Xbox-style HUD.** While you play with a pad, the in-game display is laid out like
the original Xbox version's: the action menu at the bottom left, the target at the
top left, your party at the bottom right. Use the mouse or keyboard and the PC
display is back at once. It can be switched off, to keep the PC display with a pad
as well.

**On its own.** Controller support is a separate patch. It can be installed without
the rest of KMRP, on the unchanged game or beside another widescreen mod.

## Installing and removing

- **One program.** Run it, press Start Patching, play. It finds the Steam or GOG game
  by itself.
- **The game's main file is not rewritten.** KMRP's changes are applied each time the
  game starts. Steam's copy stays exactly as Steam installed it, and you start the
  game the way you always do.
- **Your mods are left alone.** KMRP puts nothing in the `Override` folder and
  replaces no file of another mod. It was tested with the KOTOR 1 Community Patch
  and KOTOR 1 Restoration, and the order you install them in does not matter.
- **Restore Original** undoes everything KMRP did, file by file.
- **Options** (the gear button): graphics-card compatibility, the map note fixes, the
  HD item icons and controller support can each be switched off; the High FPS Fix
  can be switched on; diagnostic logs can be switched on
  when a bug report needs them.
- **An older KMRP** is replaced automatically when you patch again.
- **Update notice.** The installer tells you when a newer KMRP is out.
- **KOTOR Patch Manager users** get KMRP as two patches that sit beside their other
  patches.

## What you do not need any more

KMRP replaces these. Do not install them alongside it:

- UniWS or any other widescreen patcher
- High Resolution Menus
- a separate 4 GB patch
- KOTOR Patch Manager's own 4 GB, texture, grass, save-game and Better Movie
  Playback patches (KMRP contains them)

## Where it works

| | |
| --- | --- |
| Windows, Steam version | Yes |
| Windows, GOG version | Yes |
| Windows, disc version 1.03 | Yes |
| macOS, Steam version | Yes, since KMRP 1.5, with a separate installer (`KMRP-macOS-1.5.0.dmg`); tested on one Apple Silicon Mac, Intel Macs untested. See [macos/PLAYER-README.md](../macos/PLAYER-README.md) and [macos/README.md](../macos/README.md). |
| Linux, Proton, Steam Deck | Experimental. See [linux-proton-steam-deck.md](linux-proton-steam-deck.md). |
