# KMRP Save Editor

Opens any Star Wars: Knights of the Old Republic or KotOR II save and changes it safely.
For Windows, Linux and macOS; works with or without KMRP installed.

* **Finds your saves by itself**: Steam (any library), Steam Cloud saves of KotOR II, GOG and
  disc installs, the Aspyr Mac and Linux ports. Saves from anywhere else (a phone, a Switch,
  another PC) can be added once with Add a Save Folder.
* **Looks like the game**: the save list is the game's Load screen, with each save's picture
  and party; the editor is the in-game menu's tabs. KotOR II in its own colours; dark and
  light mode with the moon and sun button.
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
[docs/save-editor.md](../../docs/save-editor.md). The save format:
[docs/save-editor-format.md](../../docs/save-editor-format.md).

## Building

Windows: `powershell -ExecutionPolicy Bypass -File src\save-editor\build.ps1` makes
`dist\KMRP Save Editor.exe`. Linux and macOS: `sh src/save-editor/build.sh`. Both need Rust
(stable) and, to set the window in KMRP's own font, the fonts made by
`tools/build_hd_original_otf.py` (which needs the game's font atlases in `build/`; without
them the build uses the system's font and says so).

GPL-3.0-or-later, like KMRP. Created by RaymanGT.
