# KMRP Save Editor

Opens any Star Wars: Knights of the Old Republic or KotOR II save and changes it safely.
For Windows, Linux and macOS; works with or without KMRP installed.

* **Finds your saves by itself**: Steam (any library), Steam Cloud saves of KotOR II, GOG and
  disc installs, the Aspyr Mac and Linux ports. Saves from anywhere else (a phone, a Switch,
  another PC) can be added once in Settings, with Add a Save Folder.
* **Looks like the game**: the save list is the game's Load screen, with each save's picture
  and party; the editor is the in-game menu's tabs. KotOR II in its own colours; dark and
  light mode and three text sizes in Settings (the gear, top right).
* **Character**: name, experience (the game then offers the level-up itself), a second
  class, alignment, attributes, Health and Force, portrait and body, position.
* **Abilities**: skills, and feats and Force powers added or removed one at a time.
* **Inventory**: credits, components and chemicals, any item the game (or a mod) has, stack
  sizes.
* **Party**: recruited, can be picked, influence, party experience, and bringing a member
  over from another save.
* **Story**: every global variable, and a comparison with another save to fix a stuck quest;
  doors, containers and stores of the current area; the journal; the galaxy map; Pazaak
  cards; the cheat mark; the save's name.
* **Never breaks a save**: nothing is written until Save Changes, the game has to be closed,
  and the whole save is copied to a backup folder first.

Original Xbox saves can be looked at but not changed (the Xbox would call them damaged).

What it changes, field by field, and how it was tested:
[docs/save-editor.md](docs/save-editor.md). The save format:
[docs/save-editor-format.md](docs/save-editor-format.md).

## Building

This folder builds on its own; nothing outside it is needed. Windows:
`powershell -ExecutionPolicy Bypass -File build.ps1` makes `dist\KMRP Save Editor.exe`.
Linux and macOS: `sh build.sh`. Both need Rust (stable).

The window is set in the KMRP Original HD fonts: the four it uses are in `fonts/` here,
copies of KMRP's [fonts/](../fonts/README.md), under the SIL Open Font License 1.1
([fonts/OFL.txt](fonts/OFL.txt)). A folder named by `KMRP_FONTS` is used instead when it
holds all four.

The icon, a holocron with a datapad, and how to remake it: [assets/icon](assets/icon/README.md).

GPL-3.0-or-later, like KMRP; the fonts OFL-1.1. Created by RaymanGT.
