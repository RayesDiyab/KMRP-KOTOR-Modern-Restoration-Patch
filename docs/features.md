# What KMRP changes

Everything KMRP does to *Star Wars: Knights of the Old Republic* compared with the
game as it comes from Steam or GOG, in plain words. Nothing here needs technical
knowledge. The same list with how each item is done and where it lives in the code is
in [features-technical.md](features-technical.md).

The list is the Windows version's. The Mac version is the same KMRP; what differs
there is in [On the Mac](#on-the-mac) below.

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
| The resolution list is short and ignores modern displays. | The game's Screen Resolution setting lists every resolution your display supports, and you can switch between them in the game. The change is made at once, with no restart. |
| The list can show the same resolution several times over. | Each resolution and refresh rate is listed once. |
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
| Message boxes, tutorial boxes and confirmation boxes cut their text off. | Boxes grow to fit what they say, the "Journal Entry Added" and "Items Received" notice among them. |
| Some item descriptions begin with an empty line. | Descriptions begin with their text. |
| The tick circles on the options screens stay tiny at high resolutions. | They grow with the screen, and their rows with them. |
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
options either way, and its tile in the installer says what your display can do
("Display supports 120 Hz"). It is another author's work: included unchanged on
Windows, and ported to the Mac game by KMRP for the Mac version.

The frame rate itself is chosen in the game, in the same list as the resolution:
Options, Graphics, Screen Resolution shows each resolution once for every refresh
rate your display has, for example "3440 x 1440 @ 120 Hz". The original game hides
the rates above 85 Hz; with High FPS Fix they are all there and the game starts at
the highest. Without it the game is held at 60, as long as V-Sync stays on in the
game's graphics options.

## Sharper artwork

- Party portraits in high quality (by MadDerp).
- Item icons in high quality (by JackInTheBox). Optional, on by default: switched
  off, the game keeps its own icons. Every icon is drawn at the game's own size in
  its slot, so none hangs over its frame.
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
- A does the obvious thing with your target: talk, open, use, attack. Clicking the
  left stick flourishes your weapon.
- The shoulder buttons pick the previous or next target. The left trigger switches
  party member, the right trigger pauses.
- The D-pad works the action bar: pick an action, press A to use it. The bar keeps
  your place, so A again repeats the action; B lets go of the bar.
- In a fight, X disengages and Y removes the last queued action. With the
  Xbox-style HUD, B disengages as well once no action is picked.
- Start opens the map and closes the menus again, Back asks about Solo Mode, and
  clicking the right stick switches free look.
- The mouse pointer hides while you use the pad and comes back when you move the
  mouse.
- The game comes to the front when it starts, so the pad can skip the opening
  movies without a mouse click first.

**Menus.**

- The D-pad or left stick moves through every screen; A selects, B goes back.
  Holding a direction keeps moving through a long list.
- The triggers switch between the menu tabs, shown as arrows named for your pad
  (LT and RT, L2 and R2, ZL and ZR), and the right stick scrolls long text.
- An A picture follows the selection, so you can always see what A will do: down
  the main menu, on Yes or No, and on the reply you are about to give.
- Clicking the right stick switches the party member on the Character, Equipment,
  Inventory and Abilities screens. On Abilities, X switches between Skills, Powers
  and Feats.
- On the Character screen A is Level Up and Y is Auto Level Up.
- In the Journal, A switches between active and completed quests and Y changes
  the order.
- In a shop, A buys or sells and X switches between the Buy and Sell lists.
- On the options screens, D-pad left and right change a setting and Y puts the
  screen back to its defaults. The same two directions raise and lower attributes
  and skills when you create or level up a character.
- Notices such as "Journal Entry Added" and the list of new feats close with A.
- In conversations you pick a reply with the D-pad and confirm with A.
- Character creation, level-up, shops, containers, saving and loading, the options
  and Pazaak's wager are all usable without touching the mouse. In character
  creation the D-pad picks the portrait and Y is Recommended or Random Name; a pad
  cannot type, so a name of your own still needs the keyboard.
- A or Start skips a movie.

**Controller Layout screen.** Options, Gameplay has a new screen showing what every
button does, with the pictures of your pad.

**Rumble.** Three settings: off, the original Xbox version's rumble (grenades, heavy
footsteps, Force powers and the rumble BioWare made for the PC but never switched
on), or an enhanced one that adds lightsabers igniting, humming and clashing,
blaster recoil, hits taken and explosions. It is silent in menus and while the game
is paused. The setting and the strength are in `kmrp-controller.ini` beside the
game, and a change there takes effect while you play.

**Xbox-style HUD.** While you play with a pad, the in-game display is laid out like
the original Xbox version's: the action menu at the bottom left, the target at the
top left, your party at the bottom right and the minimap at the top right. Use the
mouse or keyboard and the PC display is back at once.

- Its frames, bars and boxes are drawn sharp for your resolution; the icons in
  them are the game's own.
- A paused game says "PAUSED. PRESS [right trigger] TO CONTINUE" beside the
  minimap, with the trigger of your pad (in the English game; other languages keep
  the game's own lines).
- In a fight a line across the top says that combat mode is on and which button
  leaves it.
- The marker around your target is sized for the screen.
- To keep the PC display with a pad as well, set `Style=PC` under `[Hud]` in
  `kmrp-controller.ini`, or switch the option off in KOTOR Patch Manager.

**On its own.** Controller support is a separate patch. It can be installed without
the rest of KMRP.

**Works with other interface and widescreen mods.** The controller patch puts no
file into the game's folders and replaces none of another mod's. Its button
pictures and its HUD are placed while the game runs, from the screens as they are,
so they fit whatever interface is installed. Tried on the unchanged game, with
KMRP, and beside Scaled Kotor 1.3.1, the widescreen patch by J and Vriff. Other
widescreen mods have not been tried.

## Installing and removing

- **One program.** Run it, press Start Patching, play. It finds the Steam or GOG game
  by itself and says which version it found.
- **The game's main file is not rewritten.** KMRP's changes are applied each time the
  game starts. Steam's copy stays exactly as Steam installed it, and you start the
  game the way you always do.
- **Your mods are left alone.** KMRP puts nothing in the `Override` folder and
  replaces no file of another mod. It was tested with the KOTOR 1 Community Patch
  and KOTOR 1 Restoration, and the order you install them in does not matter.
- **Restore Original** undoes everything KMRP did, file by file.
- **Options** (the gear button): controller support, graphics-card compatibility,
  the map note fixes and the HD item icons can each be switched off; the High FPS
  Fix can be switched on or off (it starts on where your display runs above
  60 Hz); diagnostic logs can be switched on when a bug report needs them. Your
  choices are remembered, and Restore Defaults puts them all back.
- **An older KMRP** is replaced automatically when you patch again.
- **Update notice.** The installer tells you when a newer KMRP is out.
- **KOTOR Patch Manager users** get KMRP as two patches that sit beside their other
  patches, and D3M0's High FPS Fixes as a third while High FPS Fix is on. Where
  KOTOR Patch Manager already looks after the game, the installer hands the
  patches to it and leaves its files alone.
- **A smaller download.** The Windows installer is about 147 MB and the Mac disk
  image about 114 MB, roughly half of what they were during development.
- **Without the window.** Everything the installer does can also be run from the
  command line.

## What you do not need any more

KMRP replaces these. Do not install them alongside it:

- UniWS or any other widescreen patcher
- High Resolution Menus
- a separate 4 GB patch
- KOTOR Patch Manager's own 4 GB, texture, grass, save-game and Better Movie
  Playback patches (KMRP contains them)

## On the Mac

New in KMRP 1.5: the Steam version of the game on macOS, with an installer of its
own (`KMRP-macOS-1.5.0.dmg`) that looks and works like the Windows one. How to
install it is in [macos/PLAYER-README.md](../macos/PLAYER-README.md).

**The same as on Windows:** the menus made for your resolution (the same 66 sets,
and any other size fitted), the sharp text, the lists, icons and popups, the map
and its note fixes, the conversation bars, the crash on long item descriptions,
the HD portraits, icons and menu art, and all of controller support, with the
button pictures, rumble, the Controller Layout screen and the Xbox-style HUD. The
Mac game has no controller support at all without KMRP.

**Different on the Mac:**

- **Retina.** The game starts at the resolution macOS is set to, and the display's
  full Retina resolution is in the game's list (3024x1964 on a 14-inch MacBook
  Pro). A change is made at once and kept for the next start.
- **Another display** is offered after the game is started again, not while it
  runs.
- **Options.** Five: controller support, the map note fixes, the HD item icons,
  High FPS Fix and diagnostic logs. There is no graphics-card compatibility option;
  that fix is for Windows.
- **High FPS Fix** is KMRP's port of D3M0's patch to the Mac game.
- **It builds on two patches by FTD,** Widescreen Patch and Stray Bug Fixes, which
  the installer brings with it. With KOTOR Patch Manager the Mac version is five
  patches.
- **The game is set to start full screen.**
- **The dialogue's reply list fills the bar at the bottom** of a conversation.
- **Needs** the unmodified Steam version of the game, macOS 10.13 or later, and
  Rosetta 2 on an Apple Silicon Mac. Tested on one Apple Silicon Mac; Intel Macs
  are untested.

**Windows only:** the fix for Windows display scaling, the extra memory for the GOG
and disc versions, the NVIDIA setting, Modern Driver Compatibility, the mouse kept
inside the game on several monitors, and the movie fixes, which the Mac game does
not need.

## Where it works

| | |
| --- | --- |
| Windows, Steam version | Yes |
| Windows, GOG version | Yes |
| Windows, disc version 1.03 | Yes |
| macOS, Steam version | Yes, since KMRP 1.5, with a separate installer (`KMRP-macOS-1.5.0.dmg`); tested on one Apple Silicon Mac, Intel Macs untested. See [macos/PLAYER-README.md](../macos/PLAYER-README.md) and [macos/README.md](../macos/README.md). |
| Linux with Proton | Tested by the maintainer on Ubuntu, with the stable Proton and with Proton Experimental: it installed and played. Other distributions are untested. See [linux-proton-steam-deck.md](linux-proton-steam-deck.md). |
| Steam Deck | Not tested on the device. It uses the same Proton, so it is expected to work the same way, and the Deck's controls are among the pads KMRP knows. |
