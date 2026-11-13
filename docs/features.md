# What KMRP changes

Everything KMRP does to *Star Wars: Knights of the Old Republic* compared with the
game as it comes from Steam or GOG, in plain words. Nothing here needs technical
knowledge. The same list with how each item is done and where it lives in the code is
in [features-technical.md](features-technical.md).

This is KMRP 1.6, released on 2026-11-13; what is new in 1.6 says so. The list is the
Windows version's. The Linux installer installs the same KMRP, and the Mac version is
the same KMRP too; what differs there is in [On the Mac](#on-the-mac) below.

KMRP changes how the game looks, fits and controls. It does not change the story,
the quests, the balance or any of the game's content, apart from one optional fix to
misplaced map notes.

## At a glance

- The game runs at your display's own resolution, including ultrawide and 4K, with
  menus and text made for that size.
- Text, lists, icons, popups, the map and the movies are all the right size and in
  the right place.
- Several crashes and glitches of the original game are fixed.
- Text, HUD and icon sizes of your choice, with a sharp HD redraw of the game's font
  (new in 1.6).
- Menus laid out as the game runs, a mod's menus included (new in 1.6).
- A controller works everywhere, with the original Xbox game's buttons and the right
  button pictures for your pad.
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
| The game's letters are small pixel drawings; enlarged, they turn soft and blocky. | **HD Font**, the default: the game's own font redrawn sharp, the same letters, sizes and spacing, sharp up to 4K at the largest text size, free under the SIL Open Font License. **Original Font** is the game's own, and **Modded Font** appears when your `Override` folder holds fonts, which are fitted to the size they are drawn at (new in 1.6). |
| Text has one size, set by the resolution. | **Text Size and Font** in Graphics Options sets four kinds of text, 50% being the original size, linked or each on its own, with Save. Text too long for its box is drawn at the largest size that fits, and lists, icons, the feat and power charts and the conversation text grow with it; the conversation bars stay as they are (new in 1.6). |
| Feat, Force power and skill icons have one size. | **Icon Size** makes them larger or smaller (new in 1.6). |
| The HUD has one size. | **HUD Size** sets each part of each HUD from 25% to 100% (twice the normal size), with a preview, for the mouse and keyboard HUD and the Xbox-style HUD (new in 1.6). |
| A mod's menu files are drawn as their author made them, usually for 640x480. | **Live Adaptive Layout:** 73 of the game's 85 menu layouts are laid out as the game runs, from the game's file or a mod's. A mod's screen already made for your size stays as it is (new in 1.6). |
| A mod that replaces a file KMRP also changes would remove KMRP's changes. | Both are kept: tables, pictures, models and layouts are merged, and the mod wins where the two disagree (new in 1.6). |
| Some shops' item list runs off the screen; the galaxy map's planets drift on wide screens. | The list stays on the screen, the planets sit where the game has them, and a mod's moved destinations are kept (new in 1.6). |
| An empty footlocker or body looks like any other. | It says "(empty)": ShaeMyName's Marked Empty Containers, with permission, on by default (new in 1.6). |
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
| Starting a movie switches the monitor to 640x480; the game can flicker, minimise or lose focus. | Movies play at the resolution the game is running at. No switch, no flicker. The game also no longer resets the screen after each movie, which may be what made the screen go black for a moment on some PCs (new in 1.6, not yet seen in the game). |
| On wide screens movies are zoomed in and cropped. | The whole picture is shown, with black bars where the movie is narrower than the screen. On a screen wider than 16:9, such as 3440x1440, movies are shown at the size they would have on a 16:9 screen of the same height, in the middle, with black around them (new in 1.6, not yet seen in the game; in 1.5 the widest movies filled an ultrawide screen and looked zoomed in). |
| Sometimes, after the startup movies, the keyboard and mouse do nothing until the game is minimised and brought back. | They keep working: the message that switched them off by mistake is dropped while the game is in front (new in 1.6, not yet seen in the game). |
| Coming back from Alt-Tab in full screen rebuilds the picture and reloads every texture, the step where players reported a freeze. | The game keeps its window, so it is back at once, with your brightness (new in 1.6; issue 96). Inspired by J's Alt Tab Patch for KOTOR Patch Manager. |

Also new in 1.6 and not yet tried on the PCs it is for: movies are
drawn with Windows' own drawing (GDI) instead of DirectDraw. This is meant to fix
movies that stay black while their sound plays, reported on Windows 7 with an AMD
graphics card (issue 48). If they are still black there, adding the two lines
`[Movies]` and `original-movie-mode=1` to `configs\kmrp.ini` in the game folder brings
back the original game's switch to 640x480 for movies. Installing KMRP again keeps
them.

## Stability

| In the original game | With KMRP |
| --- | --- |
| Opening the inventory can crash the game when an item has a long description. | Fixed. |
| The game can run out of memory in long sessions or with large texture mods. | On the GOG and disc versions the game may use twice as much memory. (Steam's version cannot take this change; the other fixes apply to it as well.) |
| Rare crashes tied to textures, grass and saving. | Fixed, using the fixes from KOTOR Patch Manager. |
| On many modern graphics cards lighting, fog, reflections, soft shadows and grass are broken or have to be switched off. | They work. This part is optional (on by default) and is Synchro's K1 Modern Driver Compatibility, 2.0.1 since 1.6, which also works under Proton and has its author's own build for Windows 7 and 8. |
| On some NVIDIA setups the menus flash white or show half-drawn pictures, and Windows Auto HDR and RTX HDR switch off. | Every frame is drawn offscreen and shown only when finished, so the menus do not flash and HDR keeps working (new in 1.6, issues 14 and 73). KMRP sets no NVIDIA option any more, and removes the one 1.5 set. |
| A saved resolution the display no longer has can stop the game from starting properly. | The best resolution the display has is used instead (new in 1.6). |

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

**Playing.** The buttons are the original Xbox game's, with its White and Black
buttons on LB and RB (new in 1.6, issue 49). In 1.5 KMRP had a layout of its own: the
shoulder buttons picked targets, the left trigger switched party member, the right
trigger paused, X disengaged and Start opened the map.

- Left stick moves your character, as slowly or quickly as you push it. Right stick
  turns the camera.
- A does the obvious thing with your target: talk, open, use, attack. X does the
  same (on the Xbox it added an action to the queue, and on the PC every action is
  queued). Clicking the left stick flourishes your weapon.
- The triggers pick the previous or next target. LB pauses, RB switches party
  member.
- The D-pad works the action bar: pick an action, press A to use it. The bar keeps
  your place, so A again repeats the action; B lets go of the bar.
- In a fight, B disengages once no action is picked, and Y removes the last queued
  action. With nothing to remove, Y flourishes your weapon.
- Start opens the menus on the screen you used last and closes them again, Back
  asks about Solo Mode, and clicking the right stick switches free look.
- The mouse pointer hides while you use the pad and comes back when you move the
  mouse.
- The game comes to the front when it starts, so the pad can skip the opening
  movies without a mouse click first, and the A that skips a movie no longer presses
  the next screen's button.
- The Xbox-style HUD's action row is the Xbox manual's six places: your own Force
  powers can be picked with an enemy targeted, and Stealth is in the row whenever it
  would work (new in 1.6, issues 50 and 55).
- A quick flick into the stick's corner no longer runs faster or the wrong way, a long
  diagonal no longer spins the character, and free look looks up and down with the
  right stick (new in 1.6, issues 45 and 46).
- **Swoop racing and the gun turret:** the left stick steers and aims; A starts,
  shifts and shoots; the triggers shoot in the turret; Start pauses. At the shift point
  the race shows the pad's button instead of "Space" (new in 1.6, issue 47).
- A Bluetooth DualSense that Steam's idle timer switched off is found again when it
  comes back (new in 1.6, issue 71).

**Menus.**

- The D-pad or left stick moves through every screen; A selects, B goes back.
  Holding a direction keeps moving through a long list.
- The triggers switch between the menu tabs, shown as arrows named for your pad
  (LT and RT, L2 and R2, ZL and ZR), and the right stick scrolls long text.
- An A picture follows the selection, so you can always see what A will do: down
  the main menu, on Yes or No, and on the reply you are about to give.
- RB switches the party member on the Character, Equipment, Inventory and
  Abilities screens (a click of the right stick in 1.5). On Abilities, X
  switches between Skills, Powers and Feats.
- On the Character screen A is Level Up and Y is Auto Level Up.
- In the Journal, X shows the quest items, Y switches between active and completed
  quests and RB changes the order (in 1.5 A and Y did the last two).
- At the Pazaak table, X plays the card you picked, LB flips it, A ends the turn
  and Y stands, as on the Xbox; the D-pad moves between the cards in your hand, and
  the side deck screen is drawn as the Xbox drew it (new in 1.6).
- The left stick walks a conversation's replies and moves the selection in character
  creation, and the galaxy map moves planet to planet with its description following
  (new in 1.6, issues 57 and 58).
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

**Choose your own buttons** (new in 1.6). On the Controller Layout screen, Remap lets you put the face buttons, the
bumpers, the triggers and the stick clicks on whichever of those buttons you like:
pick an action and press its new button. Remapping happens in a table, one row per
action with its button, the controls that cannot change listed underneath in grey. Giving a button to an action takes it from
the action that had it, which waits with an orange question mark until you give it
another, and Save works once every action has a button. Default puts the original
layout back, and Close asks before throwing away changes you have not saved. Default
is also on the screen as it opens, before Remap: it asks, then saves the original
layout straight away. The
sticks, the D-pad, Start and Back stay as they are. Your layout applies while you
play; the menus keep every button where it always is. The button pictures on the
HUD and in the pause notice show the buttons you chose. The layout is kept in
`KMRP\controller.ini` in the game folder (`kmrp-controller.ini` beside the game until
2026-10-20; it is moved there for you). A layout saved with 1.5 was made against
KMRP's old buttons and is not used: the screen opens on the Xbox layout, and you
choose yours again.

**Button pictures** are drawn from vector outlines at the exact size they are shown,
each letter centred on its button, so they are sharp at every resolution, the Steam
Deck's included (new in 1.6, issue 68). The Xbox-style HUD's frames, the tab arrows
and the Controller Layout diagram are drawn the same way.

**Rumble.** Three settings: off, the original Xbox version's rumble (grenades, heavy
footsteps, Force powers and the rumble BioWare made for the PC but never switched
on), or an enhanced one that adds lightsabers igniting, humming and clashing,
blaster recoil, hits taken and explosions. It is silent in menus and while the game
is paused. The setting and the strength are in `KMRP\controller.ini` in the game
folder, and a change there takes effect while you play.

**Xbox-style HUD.** While you play with a pad, the in-game display is laid out like
the original Xbox version's: the action menu at the bottom left, the target at the
top left, your party at the bottom right and the minimap at the top right. Use the
mouse or keyboard and the PC display is back at once.

- Its frames, bars and boxes are drawn sharp for your resolution; the icons in
  them are the game's own.
- A paused game says "PAUSED. PRESS [LB] TO CONTINUE" beside the minimap, with
  the button of your pad that pauses (in the English game; other languages keep
  the game's own lines). In 1.5 that was the right trigger.
- In a fight a line across the top says that combat mode is on and which button
  leaves it.
- The marker around your target is sized for the screen.
- To keep the PC display with a pad as well, set `Style=PC` under `[Hud]` in
  `KMRP\controller.ini`, or switch the option off in KOTOR Patch Manager.

**On its own.** Controller support is a separate patch. It can be installed without
the rest of KMRP.

**Works with other interface and widescreen mods.** The controller patch puts no
file into the game's folders and replaces none of another mod's. Its button
pictures and its HUD are placed while the game runs, from the screens as they are,
so they fit whatever interface is installed, and since 1.6 a GUI mod's own screens
get its button prompts. Tried on the unchanged game, with
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
- **One folder of its own.** KMRP keeps its own files in a `KMRP` folder in the game
  folder: your controller settings (`controller.ini`), its logs (`logs`), the copy of
  `swkotor.ini` that Restore Original puts back (`backups`), and its records of what
  it installed. Until 2026-10-20 these lay loose beside the game; patching again
  moves them. Restore Original leaves the installer's log and the `swkotor.ini` copy
  there, as it left them beside the game before. New in 1.6.
- **Options** (the gear button): controller support, graphics-card compatibility,
  the map note fixes, the HD item icons and Marked Empty Containers can each be
  switched off; the High FPS Fix can be switched on or off (it starts on where your
  display runs above 60 Hz); diagnostic logs can be switched on when a bug report
  needs them. Your choices are remembered, and Restore Defaults puts them all back.
- **Apply New Settings.** Change an option after installing and the installer changes
  only that, without installing again (new in 1.6; Windows, and the Mac).
- **An older KMRP** is offered as an **Upgrade**, which keeps your settings.
- **Safer installs.** The installer checks before it starts, refuses while the game is
  running and says so plainly, shows **Repair** when an install needs it, and an
  install that is stopped or fails leaves nothing it cannot undo (new in 1.6).
- **Windows compatibility mode** set on `swkotor.exe`, which can leave a black square
  over the game, is turned off when KMRP patches and put back by Restore Original (new
  in 1.6, issue 39).
- **Update notice.** The installer tells you when a newer KMRP is out.
- **KOTOR Patch Manager users** get KMRP as two patches that sit beside their other
  patches, and D3M0's High FPS Fixes as a third while High FPS Fix is on. Where
  KOTOR Patch Manager already looks after the game, the installer hands the
  patches to it and leaves its files alone.
- **A smaller download, and fast starts.** The Windows installer is 57 MiB (140 in
  1.5.1), the Linux installer 67 MiB and the Mac disk image 73 MiB (108 in 1.5). Every
  resolution your display offers is prepared while installing, so starts and
  resolution changes take about a second and a half (new in 1.6).
- **Linux.** A native installer, `KMRP-Linux-1.6.0-x86_64.AppImage`, finds the Steam
  game and installs, restores and prepares KMRP's art under Proton as the Windows
  installer does (new in 1.6, issue 76). The Windows installer still works there
  through Protontricks.
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

Since KMRP 1.5 the game on macOS has an installer of its own, now
`KMRP-macOS-1.6.0.dmg`, that looks and works like the Windows one. It is for the
Steam version and, new in 1.6, the Mac App Store version, which KMRP leaves unchanged
and starts through a "KOTOR with KMRP" app of its own. How to install it is in
[macos/PLAYER-README.md](../macos/PLAYER-README.md).

**The same as on Windows:** the menus made for your resolution (the same 66 sets,
and any other size fitted), the sharp text, the lists, icons and popups, the map
and its note fixes, the conversation bars, the crash on long item descriptions,
the HD portraits, icons and menu art, and all of controller support, with the
button pictures, rumble, the Controller Layout screen and the Xbox-style HUD. The
Mac game has no controller support at all without KMRP. New in 1.6, as on Windows:
Live Adaptive Layout, Text Size and Font with Modded Font, Icon Size, HUD Size, the
Xbox controls with remapping, Pazaak with the pad, Marked Empty Containers and Apply
New Settings.

**Different on the Mac:**

- **Retina.** The game starts at the resolution macOS is set to, and the display's
  full Retina resolution is in the game's list (3024x1964 on a 14-inch MacBook
  Pro). A change is made at once and kept for the next start.
- **Another display** is offered after the game is started again, not while it
  runs.
- **Options.** Six: controller support, the map note fixes, the HD item icons,
  Marked Empty Containers, High FPS Fix and diagnostic logs. There is no
  graphics-card compatibility option; that fix is for Windows.
- **High FPS Fix** is KMRP's port of D3M0's patch to the Mac game.
- **It builds on two patches by FTD,** Widescreen Patch (FTD and RaymanGT) and Stray
  Bug Fixes (RaymanGT and FTD), which the installer brings with it. FTD's updates of
  2026-11-09 bring back the menus' click sounds on the Mac and fix a crash at
  Dantooine's Ebon Hawk and in Carth's conversation.
- **Three more KotOR Patch Manager patches** come with 1.6: K1 Shader Fixes (FTD, J,
  Synchro and Vriff; fog, reflections, lightmaps, particles and bump mapping as
  Aspyr's port lost them, Steam's game only), the MP3 Playback Fix (Synchro, FTD,
  Vriff and Lane) and Anti-Crash Prophylactics.
- **Anti-aliasing** is switched off at 3840x2160 and above, without changing your
  setting.
- **The game is set to start full screen.**
- **The dialogue's reply list fills the bar at the bottom** of a conversation.
- **Needs** the unmodified Steam or Mac App Store version of the game, macOS 10.13 or
  later, and Rosetta 2 on an Apple Silicon Mac. Tested on Apple Silicon and on Intel
  Macs.

**Windows only:** the fix for Windows display scaling, the extra memory for the GOG
and disc versions, Modern Driver Compatibility, the offscreen frame, the mouse kept
inside the game on several monitors, and the movie and Alt-Tab fixes, which the Mac
game does not need.

## Where it works

| | |
| --- | --- |
| Windows, Steam version | Yes |
| Windows, GOG version | Yes |
| Windows, disc version 1.03 | Yes |
| macOS, Steam version | Yes, since KMRP 1.5, with a separate installer (`KMRP-macOS-1.6.0.dmg`); tested on Apple Silicon and on Intel Macs. See [macos/PLAYER-README.md](../macos/PLAYER-README.md) and [macos/README.md](../macos/README.md). |
| macOS, Mac App Store version | Yes, since KMRP 1.6, with the same installer. |
| Linux with Proton | Since 1.6 with a native installer (`KMRP-Linux-1.6.0-x86_64.AppImage`), run by the maintainer on SteamOS; the Windows installer works there too, through Protontricks. **SteamOS: tested and working with 1.5.1** (the maintainer, SteamOS 3.8 on a desktop PC with an NVIDIA RTX 3080, Proton 11.0, 2026-10-12: installed, played with a controller, resolution changed in the game, restored). Ubuntu: tested with a development build of 1.5, with the stable Proton and with Proton Experimental. 1.5.0 does not start under Proton. Other distributions are untested. See [linux-proton-steam-deck.md](linux-proton-steam-deck.md) and [linux-appimage-installer.md](linux-appimage-installer.md). |
| Steam Deck | Not tested on the device. It runs SteamOS and the same Proton, so it is expected to work the same way, and the Deck's controls are among the pads KMRP knows. |
