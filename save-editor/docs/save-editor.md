# KMRP Save Editor: what it reads, what it writes, field by field

Reference, 2026-10-22, following the [documentation standard](../../docs/documentation-standard.md).
This covers the KMRP Save Editor in [`save-editor`](../README.md): a
separate program, not part of the KMRP installer or patch, that opens KotOR 1 and KotOR 2
saves and changes them. The save format itself (every file, struct and field, with where
each fact was measured) is in [save-editor-format.md](save-editor-format.md); this document
says which of those fields the editor changes, under which rules, and how that was checked.

Provenance: the format facts come from real saves read on the maintainer's PC (ten KotOR 1
saves, four KotOR 2 saves), the installed games' own tables, and the maintainer's own
(private) reverse engineering of the KotOR 1 executable for what the engine reads and
recomputes when a save loads. Nothing comes from the code of KSE (KotOR Savegame Editor)
or its forks: KSE was used only as a list of what players expect an editor to do and of the
bugs they reported. Untested parts are marked **untested** where they are described.

## The build this describes

| | |
| --- | --- |
| Source | `save-editor` (Rust 2021, Slint 1.18 with its software renderer and the winit backend) |
| Toolchain | rustc 1.99.1 (2026-10-13), cargo 1.99.1 |
| Windows build | `save-editor\dist\KMRP Save Editor.exe` from `save-editor\build.ps1` (size and SHA-256 printed by the script) |
| Linux and macOS builds | `save-editor/build.sh`; **not built or run yet** (no Linux or Mac machine here) |
| Fonts | the KMRP Original HD fonts ([fonts/](../../fonts/README.md), SIL OFL 1.1): Menu, MenuMedium, MenuSmallB and Descriptions, committed in `save-editor/fonts` and embedded at build time ([build.rs](../build.rs)). *Corrected 2026-10-22:* until then they were the traced OTFs from `tools/build_hd_original_otf.py`, made from the game's atlases and never committed |
| KotOR 1 tested | Steam, `swkotor`, with KMRP and K1CP 1.10.0; and the KPM test copy `build/party-roster-kpm-check/game` |
| KotOR 2 tested | Steam, German release, TSLRCM 1.8.6, saves in `cloudsaves\<account>` |

## 1. What the engine does with a save

The parts that decide what an editor may change (measured; sources in
[save-editor-format.md](save-editor-format.md), sections 3.4 and 8):

| Field | Read when the save loads? | So the editor |
| --- | --- | --- |
| `Str`..`Cha`, skills `Rank`, `FeatList`, `KnownList0`, `Experience`, `GoodEvil`, `HitPoints`, `ForcePoints` | read | changes them |
| `MaxHitPoints`, `MaxForcePoints`, `PregameCurrent`, saving throws, `ArmorClass`, item `Cost` | **not read; recomputed and written back** | never changes them; shows them for reference only |
| `CurrentHitPoints`, `CurrentForce` | read, **relative to the base** (`current + (max - base)`) | "Heal Everyone Fully" sets them equal to `HitPoints` and `ForcePoints` |
| The player's level | recomputed from `ClassList` and one `LvlStatList` record per level | a level is added only through a class, with its record (section 4) |

The player exists in `Mod_PlayerList` of the last module's `Module.ifo` (both games) and, in
KotOR 2, also as `pc.utc` in `SAVEGAME.sav`. A party member exists as `AVAILNPCn.utc`, and a
second time in the area's creature list when they stand there (the Ebon Hawk in the
GalaxyMap save holds all seven recruited members twice, with identical stats).

## 2. Where saves are found

Nothing is configured. On every start the editor looks in every place below and lists what
is there; Add a Save Folder in Settings adds any other folder (a save, a folder of saves, or a game
folder) and remembers it.

| Where | Path | Tested here? |
| --- | --- | --- |
| Steam libraries | every `path` in `<Steam>/steamapps/libraryfolders.vdf`, for the Steam root in the registry (`HKCU\Software\Valve\Steam\SteamPath`), Program Files, `~/.steam/steam`, `~/.local/share/Steam`, the Flatpak Steam and `~/Library/Application Support/Steam` | yes, Windows: KotOR 1 on C:, KotOR 2 on a second library on D: |
| Game folder saves | `<game>/saves` (any case) | yes, KotOR 1 |
| KotOR 2 Steam Cloud | `<game>/cloudsaves/<account>/`, marked CLOUD | yes |
| KotOR 1 Steam Cloud | Steam syncs `<game>/saves` itself; nothing separate | yes (no separate folder exists) |
| GOG and the discs | registry: GOG ids 1207666283 and 1421404581; `BioWare\SW\KOTOR`, `LucasArts\KotOR2` | **untested** |
| Windows VirtualStore | `%LOCALAPPDATA%\VirtualStore\<path without C:\>\saves` for a game under Program Files | **untested** |
| Aspyr ports | KotOR 1 Mac: `~/Library/Application Support/Knights of the Old Republic/saves` and the App Store container; KotOR 2 Linux: `~/.local/share/aspyr-media/kotor2/saves`; KotOR 2 Mac: two Application Support paths | **untested**; paths from Aspyr's FAQ ([save-editor-format.md](save-editor-format.md), section 6) |
| Phone, Switch, another PC | Add a Save Folder | **untested** (no such saves here) |
| Original Xbox | recognised by `SaveMeta.xbx` or `SaveImage.xbx`; opened to look at, never written (section 6) | **untested** |

Which game a folder holds: its executable or ini (`swkotor2.*` is KotOR 2), else the size of
`chitin.key`; which game a save belongs to: KotOR 2's `savenfo.res` has `PCNAME`,
`STORYHINT0` or `TIMESTAMP`, KotOR 1's never does. When both games are installed the list
opens on the one used last, and one button switches; KotOR 2 then gets its own colours.

## 3. Every value the editor writes

"Copies" means every copy of the creature the save holds (section 1). All names in lists come
from the installed game (its `dialog.tlk` and tables, with Override, KotOR 2's Override
subfolders and its Steam Workshop folder first), so a German game shows German names and a
modded game shows its mods.

| Screen | Value | File and field | Rule |
| --- | --- | --- | --- |
| Character | Name (player) | `FirstName` and `Mod_FirstName` (the text, StrRef -1); `LastName`, `Mod_LastName` cleared; KotOR 2 also `PT_PCNAME` and savenfo `PCNAME` | Windows-1252; other characters become `?` |
| Character | Experience | `Experience` | at least 0; buttons set the next level's or the highest level's XP from `exptable.2da` |
| Character | Alignment | `GoodEvil` | 0 to 100 |
| Character | Attributes | `Str` `Dex` `Con` `Int` `Wis` `Cha` | 1 to 100 |
| Character | Add a Class | a second `ClassList` entry at level 1, its hit die added to `HitPoints` and `CurrentHitPoints`, its Force die to `ForcePoints` and `CurrentForce`, for the player one more `LvlStatList` record, XP raised to the new level if short | only when there is one class; droids get droid classes only |
| Character | Look | `PortraitId`, `Appearance_Type` (the portrait's body in the current build: `appearance_s`, `appearancenumber` or `appearance_l` of `portraits.2da`), `Gender` | portraits with `forpc` 1 |
| Character | Position (player) | `XPosition`, `YPosition`, `ZPosition` | numbers only |
| Character | Heal Everyone Fully | `CurrentHitPoints = HitPoints`, `CurrentForce = ForcePoints` for every creature | |
| Abilities | Skills | `SkillList[i].Rank` | 0 to 99 |
| Abilities | (how they are shown) | every feat and Force power the game has is listed, each with its icon (feat.2da `icon`, spells.2da `iconresref`), in groups: feats by `toolscategories` (Jedi, Combat, Weapons and armour, Class abilities, Skills and general, Droid and other), powers by `goodevil` (Universal, Light side, Dark side), a chain's links together in order; what the creature has is lit | names, icons and groups come from the game and Override, so modded feats and powers appear with their own icons |
| Abilities | Feats | `FeatList`: add one entry, or remove one and the same feat from every `LvlStatList[].FeatList` | a new entry is a copy of an entry already there |
| Abilities | Force powers | `ClassList[j].KnownList0` of the class that has powers (else the first Force class): add one, or remove one and the same power from every `LvlStatList[].KnownList0` | only a creature with a Force class; powers are `spells.2da` rows with `usertype` 1 |
| Inventory | Credits | `PT_GOLD` | at least 0 |
| Inventory | Components, Chemicals (KotOR 2) | `PT_ITEM_COMPONEN`, `PT_ITEM_CHEMICAL` | |
| Inventory | Stack | `StackSize` | 1 to `baseitems.2da` `stacking` |
| Inventory | Remove | the `ItemList` entry of `INVENTORY` | |
| Inventory | Add an Item | a new `ItemList` entry built from the item's `.uti` (template-only fields dropped, save-only fields shaped like an item already in the save) | every `.uti` in the game and Override |
| Inventory | (icons, kinds, Add Item) | an item's icon is `i` + its base item's `itemclass` + `_` + its `ModelVariation` in three digits (iw_lghtsbr_001), else the base item's `defaulticon`; the inventory and Add an Item have a tab per kind (two rows of tabs when the window is too narrow for one), and Add Item is a full-width bar under the list, chosen by the maintainer from four rendered placements so it never covers a row; (Weapons, Grenades, Armour, Gear, Usable, Upgrades, Other) from baseitems.2da `equipableslots`, `itemclass` and `defaulticon`; creature-only items are left out | the rule matched all 40 items checked in the GalaxyMap save; Override textures (TPC or TGA) come first, so modded icons show |
| Party | Recruited | `PT_AVAIL_NPCS[n].PT_NPC_AVAIL` | only when the save holds `AVAILNPCn` |
| Party | Can be picked | `PT_AVAIL_NPCS[n].PT_NPC_SELECT` | |
| Party | Influence (KotOR 2) | `PT_INFLUENCE[n].PT_NPC_INFLUENCE` | 0 to 100; hidden for someone not met (-1) |
| Party | Bring or Replace from Another Save | `AVAILNPCn.utc` copied from another save of the same game, recruited and selectable | the other save must hold that member |
| Party | Party experience | `PT_XP_POOL` | members who join later catch up to their share of it |
| Story | Global variables | `ValBoolean` bit `7 - i % 8` of byte `i / 8`; `ValNumber` byte `i` (shown -128 to 127); `ValString[i]` | the catalogue lists are never reordered |
| Story | Compare with Another Save | read only; "Take" copies the other save's value of one variable, "Take All Theirs" every differing one | matched by name and kind |
| Story | Doors | `Locked` (unlocking also clears `KeyRequired`), `OpenState` (opening also unlocks) in the area's `Door List` | |
| Story | Containers and stores | `ItemList` of a placeable (new items get an `ObjectId` above every id in the area) or a store (items numbered by position, `Infinite` kept when the store uses it) | |
| Story | Journal | removes an entry of `JNL_Entries` | the story switches stay as they are |
| Story | Galaxy map | `GlxyMap.GlxyMapPlntMsk`: bit *i* and bit *i*+16 together | rows of `planetary.2da` |
| Story | Pazaak side cards | `PT_PAZAAKCARDS[i].PT_PAZAAKCOUNT` | 0 to 9 |
| Story | Marked as cheated | `PT_CHEAT_USED` and savenfo `CHEATUSED` | |
| Story | Save name | savenfo `SAVEGAMENAME` | |

When `PARTYTABLE.res` changes, savenfo's `TIMEPLAYED`, `CHEATUSED` and (KotOR 2) `PCNAME`
are written from it again, so the Load screen agrees with the save.

## 3a. What KSE edits, and where it is here

Taken from KSE 3.3.7's readme (its list of editable fields), not from its code.

| KSE | Here | Rule |
| --- | --- | --- |
| Equipment (player and party) | Inventory, Equipped by | an item taken off goes to the party inventory and the effects whose `CreatorId` is its `ObjectId` go with it; an item put on gets `Mod_NextObjId0` of the module's `Module.ifo` as its object id, which then moves on; only items whose `equipableslots` has the slot and whose `droidorhuman` (1 people, 2 droids) fits |
| Current Party | Party, With you | `PT_MEMBERS`, `PT_NUM_MEMBERS`, savenfo `PORTRAIT1`/`PORTRAIT2`; the area is left alone |
| Levels, Class add/remove/change | Character, Classes, Edit | `set_class_level`, `change_class`, `remove_class` in `src/creature.rs`; one level record per level for the player |
| Hit Points, Force Points (current and max) | Character | the current value as the game shows it is stored relative to the base; the maximum moves the base (and the player's last level record) |
| Min1HP | Character, Cannot die | `Min1HP` |
| Appearance, Gender, Soundset, Portrait, NPC name | Character, Look and voice | `Appearance_Type`, `Gender`, `SoundSetFile`, `PortraitId`, `FirstName` |
| Time played | Story, More | `PT_PLAYEDSECONDS` (savenfo follows) |
| Quests | Story, Quests | `JNL_Entries`: a quest at a stage of global.jrl |
| Copy inventory between saves | Inventory, Copy from Another Save | the other save's `INVENTORY` item list |
| Xbox .sig files | not done | see section 6 |

Area creatures (in the fork the maintainer showed) are listed in Story, Creatures, with a
remove cross.

## 3b. The map, moving the player, Finish Quest

| What | How |
| --- | --- |
| The picture | `lbl_map<area>` from the GUI texture pack or Override (KotOR 1 also without the planet prefix), its left 440 of 512 pixels |
| World to map | the .are `Map` struct: scale per axis from `WorldPt1/2` and `MapPt1/2`, axes swapped for `NorthAxis` 2 and 3 (`Calibration` in `src/map.rs`); checked against the game: markers in their rooms on Tatooine, the Ebon Hawk, Citadel Station (KotOR 2) and the Jedi Enclave (`NorthAxis` 3) |
| The arrow | `mm_barrow`, turned by the angle the player's `XOrientation`/`YOrientation` makes on the map; matched the game's arrow at 90 and 180 degrees |
| Markers | round badges drawn in the editor (so they stay round whatever the renderer clips): a person's portrait (portraits.2da `baseresref`), else the game's icon: `i_opendoor` door, `ig_areatrans` way out (KotOR 2 only; KotOR 1 shipped no walking figure, so `gui_mp_doorU`), `i_openplace` container, `i_useplace` thing to use, `i_dialog` person, `whitetarget` map note; the ring's colour says the kind |
| Zoom | 1x to 6x with + and - beside the map or the wheel (about the pointer); zoomed in, a drag moves the view; markers keep their size |
| Floor | every room of the area's .lyt, its .wok faces whose material has `walk` 1 in surfacemat.2da; a spot must have floor under it and under eight points 0.45 m around it, within 0.6 m of its height |
| Spots | things to use and containers: in front (their `Bearing`), then round the sides, 1.1 to 2.4 m out; people who talk: 1.3 m out; doors: 1.2 to 2.6 m out on each side; ways out without a door: the trigger's middle; a clicked point: the nearest spot within 1.5 m |
| Moving within the area | `XPosition`/`YPosition`/`ZPosition` of every player copy, facing the object |
| Moving to another area | only areas in SAVEGAME.sav; the player goes into that module's `Mod_PlayerList` with that module's player `ObjectId` and `AreaId`, its items new ids from `Mod_NextObjId0`, effects re-pointed; savenfo `LASTMODULE` and `AREANAME` |
| Spawn a Creature Here | on a picked floor spot in the area the save resumes in: a copy of a creature standing there, or any creature template the game has (its templates and Override, and the area's own module templates), in tabs In This Area, Hostile, Friendly, Other (by `FactionID` in repute.2da); it faces the player; a new one runs its own spawn script when the save loads ([save-editor-format.md](save-editor-format.md), section 5.2) |
| Finish Quest | the quest's stages with `End` 1 in global.jrl; XP = plot.2da `xp` x the stage's `XP_Percentage`, added to `Experience` and `PT_XP_POOL` when the stage is new |

**Travel and Skip Ahead** (2026-10-23; played by the maintainer in KotOR 1):

| What | How |
| --- | --- |
| Any area | The Map tab's Areas list holds every area of the game, by planet (cutscene stages, `stunt_` modules, and nameless modules left out; of two areas with one name the visited one, else the one a door leads into). An area not visited shows the game's own .git with each object's template fields filled in (names, portraits) |
| Travel Here | The ways the game's doors and transitions lead into the area (each module's shipped .git, `LinkedToModule` and `LinkedTo`). Picking one queues an area-transition event (`EVENT_AREA_TRANSITION`, 26) first in the current module's `EventQueue`, due at the saved moment: the game makes the trip right after the save loads, loads an unvisited area fresh from its files with its arrival scripts, and brings the party (`Save::queue_transition`; the event's layout from the maintainer's own reverse engineering, handler 0x0050D6C0). *Corrected 2026-10-23:* queued last and a second later, it waited behind the save's own delayed events until the player did something |
| Skip Ahead | Story, Skip Ahead: a chapter as if played (`questdb::skip_to`). The chapter's milestone (`data/quests/*-milestone.json`): journal, the story values the rest of the game reads, items; its rewards (`*-rewards.json`, `tools/questdb/rewards.py`): the XP of a full run (kills by the engine's rule, plot XP, script XP, SetXP floors, `tools/xp/calc.py`), the enemies' Dropable items and the containers' loot (class gear by the game's own tests); then the trip by the game's own first hop with its movies, so the story plays on (from the Endar Spire: escape pod movie 01c, the vision, then the Taris apartment) |
| Kill XP | The engine on every death (`ApplyDeathExperience` 0x004FB1E0): xptable.2da row (player level from XP) column trunc(CR), for a creature whose faction's reputation toward the player is 10 or below; the player all of it, party members 80%, the pool all of it. Checked against two Endar Spire saves (150 and 450 XP at the same points) |

**The whole of KotOR 1** (2026-10-23, mapped by `tools/questdb`, `checked: false`): 12
chapters (Endar Spire, Taris, Dantooine, Tatooine, Kashyyyk, Manaan, Korriban, Leviathan,
Unknown World, Star Forge, and the Ebon Hawk and Yavin Station as side chapters), each with
its quest file, milestone, rewards and XP scenario, in `data/quests` and `data/xp`, IDs only
(no game text: names and journal text are looked up from the player's own game; the readable
review pages go to the ignored `data/quests/local`). Skip to Here applies every main chapter
before the picked one that the save has not played, in story order, then the picked one:

| Applied per chapter | How |
| --- | --- |
| Journal | the chapter's stages, then the quests the game itself removes (`journal_remove`) |
| Story values | the milestone's globals |
| Star maps | `K_STAR_MAP` counted the game's way (10 and 10 a planet whose map is found) and what reaching a count sets (the Leviathan capture after the third, the Unknown World after the fourth) |
| Items, loot | held items, the enemies' Dropable items, the containers' loot (class gear by the game's tests); credit chips (base item 57) add their stack size to the party's credits |
| Credits, alignment | what the chapter's conversations and scripts pay and take, for a light-side and for a dark-side run (`tools/questdb/credits.py`, in the rewards file's `credits`), plus the payments the main path cannot avoid (`credits_fixed`: the droid on Taris, the assassin droid on Tatooine); the alignment moves by the side's points, never toward the other side |
| Light or dark | asked in the confirmation when it changes anything (`side_matters`), the player's current leaning first; the dark side applies the chapter's `dark` block where the story branches: on Dantooine slot 5 is killed, not recruited; at the temple summit slot 0 rejoins and slots 4 and 5 are lost, then slots 2 and 6 leave the ship; the Star Forge plays the dark-side ending |
| Companions | recruited from their templates into their slots (AddAvailableNPCByTemplate), removed where the story removes them |
| Jedi class | the player's pick in the confirmation: `DAN_PATH_STATE`, a level of the class, its lightsaber |
| XP | the cumulative full-run total at the end of the picked chapter, never lowered |
| Areas | every area of every chapter the player can return to is stored as played through (`src/stored.rs`): each object a full struct as the game stores a left area, one-time enemies omitted, doors on the path open and unlocked, looted containers empty, the area's, module's and objects' local flags as a run leaves them; never over an area the save has been to; only for save groups the trip on keeps (modulesave.2da) |
| The trip | the last chapter's own route on, with its movies |

Checked without the game (2026-10-23): a played-through copy of every one of the 117 modules
builds and reads back (`played_through_copies_of_every_module`), and a synthesized `danm14ad`
matches the copy the game itself stored in a real save list for list and field for field (but
for fields the game recomputes on load); companions from templates write and read back
(`recruit_from_template_survives_a_write`); a new save skipped to the end of Dantooine, of
Korriban and of the Star Forge reads back with the XP (53,690; 156,320; 207,440), the
companions, the class and lightsaber, the stored areas and the trip; a save on the Endar Spire
skipped through the whole game on each side reads back with that side's ending, party,
alignment and more credits (`skip_whole_game_on_each_side`). **Not yet seen in the game:** any
chapter after the Endar Spire; a return to a stored area; companions from templates; the
credits and the dark side.

How credits.py models a run, per conversation: a node's own effect is what its scripts pay,
take and shift; where the player picks a reply, one with a condition (a bounty handed in) is a
situation the run meets and counts, unless it costs credits or leans to the other side, and of
the free replies the run takes one that costs nothing if it can, then the side's way, then the
most credits; where the game picks a line, the best one (a persuade check passed); every
starting line counts (later visits), each node once. Gambling is left out. Per KotOR 1 chapter
(light / dark): Taris 2,980 / 4,005; Dantooine 2,900 / 3,000; Tatooine 2,470 / 2,590; Kashyyyk
1,900 / 2,150; Manaan 7,600 / 9,300; Korriban 1,500 / 1,500.

**KotOR 2** (2026-10-23) is mapped the same way, from the game's own files (Steam 1.0.2), in
eleven chapters: Peragus, Telos, Nar Shaddaa, Dxun, Onderon, Dantooine, Korriban, The Jedi
Masters (the enclave meeting and the return to Telos), Ravager, Malachor V, and the Ebon Hawk as
a side chapter (`tools/questdb/chapters_k2/`). What differs from KotOR 1:

| | How |
| --- | --- |
| Conversation scripts | KotOR 2 nodes run two scripts with five numbers and a string each (`a_global_set`, `a_givecredits`); the tools run them with those values bound (`tools/questdb/nodescript.py`, `ncsvm` params), so the values become constants |
| The masters found | `000_Jedi_Found`, a number each free planet raises by one (`increments`); at 4 the game itself calls the party to the enclave |
| Companions | by the player's gender (slot 4 for a male player, slot 11 for a female one) and side (slot 7 light, slot 10 dark); a template only in an area's own files is read from that area |
| Items | many loot and quest items exist only in an area's own files; Skip Ahead finds them in the chapter's areas |
| Kill XP | read from swkotor2.exe 1.0.2 (`CalculateDeathExperience` at 0x00575B20): KotOR 2's tables, the row and column capped at 31, and an autobalanced creature (`MultiplierSet`, 316 of the 333 hostile kinds) counted at the player's level when it spawned plus its `autobalance.2da` crmod (`tools/xp/calc.py`) |
| The trip | the save's event queue loads event 26 with the same layout as KotOR 1 (swkotor2.exe 0x005205F0) |

A full KotOR 2 run reaches 249,610 XP; light / dark credits by chapter: Telos 8,545 / 9,545,
Nar Shaddaa 4,550 / 8,953, Onderon 37,475 / 42,475 (each side's ruler pays the war's reward,
`credits_side_only`), Dantooine 12,000 / 13,575. Checked without the game: a save on Peragus
skipped through the whole game on each side reads back with the masters found, the XP, the
companions by gender and side, and more credits (`skip_whole_k2_game_on_each_side`). **Before
it ships:** nothing of KotOR 2 has been seen in the game. Quest XP takes one route per quest
(of the stages in the same group of ten, the best paying), and autobalanced enemies are counted
at the player's level on entering their area.

**As a real run leaves it, nothing twice** (2026-10-23, both games). Skip Ahead closes each
skipped chapter's own quests at the ending a run reaches (journal, story values, the NPCs' own
flags, doors, people who leave; `close_quests`), so their people do not offer them again; it
brings the areas the save has already been to to the played state too (one-time enemies gone,
doors open, looted containers emptied, flags set; `reconcile_visited`); and it leaves out what
the save already had: containers it emptied, drops of enemies it killed, conversations whose
quests it finished (their credits, alignment and influence), purchases whose companion it has
(T3-M4, HK-47, KotOR 2's HK chassis), story items and the Jedi lightsaber it holds, a KotOR 2
master who already taught (`master_met`). Checked: a chapter applied twice pays little the
second time and gives no item twice (`a_chapter_does_not_pay_twice`). KotOR 2's per-object
flag table holds 160 flags and 32 numbers (KotOR 1: 96 and 8); played-through areas use the
game's own size.

**KotOR 2 party and powers** (2026-10-23): influence per companion from the conversations of
each chapter (`ModifyInfluence`, the run's replies preferring what a companion likes), added to
`PT_INFLUENCE`; the masters' teachings by the game's own rule (`a_give_form`: class, prestige
class, `G_PC_FORM`, side, forms known; spells.2da 261 to 268); Force Chain on Peragus, Force
Enlightenment or Force Crush at the enclave; the prestige class Kreia offers from level 15,
picked in the confirmation (`a_pc_jedi`: the class added, `000_Prestige` 2); and, if the
player picks it, the companions trained as Jedi without their conversations (the class
`a_makejedi` gives and the values their conversation chains end with).

The data pipeline caches each script's analysis on disk (`ncsvm.run_script`, in
`save-editor/build/questdb-cache`, keyed on the script, its parameters, the interpreter's
settings and its code), so a chapter rebuild takes minutes, and `rewards.py` works out the
chapters' credits in parallel.

Seen in the game: the Endar Spire skip from a fresh save gave 3,085 XP, the level-ups, the
loot, the escape pod movie and the vision, and the Taris apartment with Carth's opening.
**Not known:** random treasure rolled by scripts at death (left out); chapters after the
Endar Spire (Taris is drafted, without a milestone yet); KotOR 2.

**The quest tracker** (Story, Quests; 2026-10-22, the maintainer: "what a person wants when
he enters the story mode ... is a quest tracker"): Story opens on Quests, listed first before
the modder sections, and the party list steps aside. Left: the quests in three tabs, Active,
Completed (the journal entry is one of the quest's endings) and Not Started, each with where it
stands. Right: the picked quest, its current journal entry in full, and every stage as a
timeline (earlier stages filled, the current one a gold ring, later ones empty, endings
tagged, each with its XP); clicking a stage puts the quest there. Finish Quest opens a pop-up
listing the endings with their XP; the chosen one is set and its XP given to the player and
the party pool, once. The journal keeps only a quest's current stage, so "earlier" means a
lower stage number, not a stage the player is known to have seen.

**Removing what was spawned** (2026-10-22): a creature the editor spawned, picked on the map,
offers Remove This Creature; the area's own creatures do not (Story, Creatures still lists
every creature for modders). The editor records each spawn in `spawned.txt` beside its
settings as game, module, `ObjectId` and `Tag`; the game keeps a creature's id when it saves,
so the record finds it in later saves of the same playthrough. Creatures spawned before this
record existed (the first test Gamorrean) are not in it. Checked in the editor: a spawned copy
offered Remove, the area's own creatures did not.

**Spawning, tested** (2026-10-22): a template creature and a copy went into copies of four
KotOR and four KotOR II saves (`tests/edits.rs`), were written and read back: both there, the
new one with `CreatnScrptFird` 0, every creature and item id owned once. **Seen in the game**
(KotOR 1, 2026-10-22, by the maintainer): a Gamorrean spawned on the Ebon Hawk stood there
when the save loaded. **Untested in the game**: KotOR 2, whether the spawn script visibly runs, a template made for another module (its
conversation and scripts may be missing there), copies of story characters (scripts find
creatures by tag).

**The layout** (2026-10-22, the maintainer: "make the map the biggest thing"): on the Map tab
the party list steps aside and the map's frame fills the panel, the picture as large as fits;
a narrow rail on the right holds the area's name and a switch between Picked, Areas and Stuck?.
Picking anything on the map shows Picked; Spawn a Creature is always there, greyed until a
floor spot is picked. Over the map the pointer is a crosshair the editor draws in the accent
colour with a dark edge (the system crosshair is drawn inverted, so it looked see-through).

**Equipped** (Inventory tab, 2026-10-22): the game's equip screen, its slots three across in
the order of equip.gui (Implant, Head, Hands; Left arm, Body, Right arm; Left weapon, Belt,
Right weapon; KotOR II's second weapon set as a fourth row, equip_p.gui), each drawn as the
shape of the game's slot frames (lbl_top, lbl_mid, lbl_bot) so the rows interlock as in the
game. An empty slot shows the game's own picture of what goes there (`iimplant`, `ihead`,
`ihands`, `iforearm_l`, `iarmor`, `iforearm_r`, `iweap_l`, `ibelt`, `iweap_r` from the GUI
texture pack) on a faint accent fill; a worn item sits on the plain frame. Clicking a slot turns the list beside it into the party's items that fit (baseitems.2da
`equipableslots` and `droidorhuman`), each with Equip, and shows what is worn there with Take
It Off. In the editor, Revert and Save Changes sit at the top
right beside the settings button, with a line under them saying what is changed or what the
last save did; the backups folder, the version and the credit moved into Settings, so the tabs
reach the bottom of the window.

Not done, on purpose: walking through walls. A save only holds where things are; letting the
player pass through doors and walls would be a change to the running game (a KMRP patch),
not to the save. Open Every Door Here unlocks and opens the area's doors instead.

## 4. The bugs other editors had, and what this one does

From KSE's issue tracker and the forums ([sources](save-editor-format.md#6-save-locations-by-platform)):

| Reported against KSE | Here |
| --- | --- |
| Removing one Force power removed all of them (KotOR 2) | removes exactly one entry, from the class list and the level records; test `edits_survive_a_write` removes one of a save's powers and checks one fewer remain, in all 14 saves that have two or more |
| No way to add or remove Force powers | both, searched by name |
| Raising the level added the wrong Vitality (KotOR 1) | no level box: XP is raised and the game's own level-up runs, with its own hit dice and choices; a class added here adds exactly its hit die and, for the player, the level record the game sums Health from |
| Max HP and FP edits thrown away | not offered as edits (section 1); the screen says what they come from |
| Inventory edits failed on commit | items are built from the game's templates and shaped like items already in the save; tested by adding two items to a save and loading it in the game |
| Saves not found: Steam Cloud, `kse.ini` paths, registry, VirtualStore, Linux | section 2, no configuration |
| Android KotOR 2 saves | Add a Save Folder; **untested** |
| Party member cannot be copied between saves | Bring from Another Save |
| No comparison of two saves' globals | Compare with Another Save |
| Override subfolders ignored (KotOR 2) | read, with the Workshop folder |
| Save pictures, player position, doors, containers, stores (nadrino's fork) | all here |

## 5. How a write stays safe

1. **Nothing is written until Save Changes.** Every change is held in memory; the bottom bar
   counts them, and Revert reads the save from disk again. Leaving a save with changes not
   saved is refused with a message.
2. **The game must be closed.** Save Changes checks for `swkotor.exe` / `swkotor2.exe`
   (`tasklist`; `pgrep` elsewhere) and refuses while it runs.
3. **A backup first.** The whole save folder is copied to
   `Save Editor Backup/<save folder>/<date time>/` in the folder that holds the save (the
   game's `saves` folder) before anything is written; a KotOR 2 Steam Cloud save's backup
   goes to the game's local `saves/Save Editor Backup` instead, so Steam does not upload it.
   After a save the editor says "Saved! Backup of the unedited save is in" and the folder.
   *Corrected 2026-10-22:* backups were kept in `<data>/KMRP/Save Editor/backups/` until the
   maintainer asked for them beside the saves. **Untested**: whether the game's Load screen
   ignores the `Save Editor Backup` folder (it holds no `savenfo.res` of its own).
4. **Only the changed files**, each written in full to `<name>.kmrp-new` first; only when
   every new file is written are they moved over the old ones.
5. **Lossless files.** GFF and ERF are read into a tree that keeps every field, its type,
   its order and every struct id, and written back from it. Test `every_save_round_trips`
   reads, writes and reads again every GFF and archive (nested module saves included) of
   all 14 saves on this machine and compares the trees: all equal. Byte identity is not
   claimed: the engine orders its struct table differently (1 or 2 of 9 to 74 GFFs per save
   came back byte for byte), which the game does not depend on.

## 6. Limits

| Limit | Why |
| --- | --- |
| Original Xbox saves are read only | the Xbox checks a signature on each save; re-signing needs the console's and the title's keys, and no verified procedure for KotOR was found. The maintainer chose (2026-10-22) to re-sign with keys read from the player's own files; **not built**: there is no Xbox save or game here to test it with |
| Nintendo Switch saves | open if they are plain PC-format folders; a compressed wrapper, if the Switch uses one, is not documented and not handled |
| Global variable list shows 200 rows at a time | drawing every row of 1,185 slowed the tab by over a second; typing part of a name narrows it |
| Names typed into the game | Windows-1252 only, as the Western releases store them |
| Two classes | the engine knows two |

## 7. What is deliberately not changed

* `MaxHitPoints`, `MaxForcePoints`, saving throws, `ArmorClass`, item `Cost`, `CombatInfo`:
  recomputed by the game (section 1).
* `EffectList`: equipment bonuses are effects created by the items; changing one without the
  other would leave the stats out of step. Equipment is not listed or changed; the game
  equips (an earlier build listed it read only; the maintainer asked why, and it went).
* The active party (`PT_MEMBERS`, `PT_NUM_MEMBERS`): who stands with the player is the
  game's to arrange; Recruited and Can be picked decide who can be chosen.
* Removing a class, lowering a level: no reliable way to undo what the level-ups granted.
* `ObjectId`s of existing objects, `Mod_NextObjId`, struct ids, field order, labels.
* Stale player copies in the other modules' `Module.ifo`: the game reads the last module's.
* Steam Cloud: nothing in Steam is touched; Steam sends the changed files itself.

Rejected along the way, and why:

| Tried or proposed | Why not |
| --- | --- |
| A tile dashboard (the first mockup) | the maintainer: "I dont want it to be tiles"; replaced by the game's in-game-menu shape, tabs and the party down the left |
| C++ with SDL3, .NET like the Font Converter, Tauri | the maintainer chose Slint: native on all three systems, no web view, runs under Wine |
| Arimo and system fonts | the maintainer: use KMRP's own fonts, the HD Original OTFs |
| Reading the GUI texture pack whole for the portraits | 300 MB of memory; the archive's index is read and each portrait read on its own (59 MB with a save open) |
| A level box | the KSE Vitality bug; see section 4 |

## 8. Verifying by hand, and what was verified

Automated (`cargo test --release` in `save-editor`, all passing 2026-10-22):

| Test | What it checks |
| --- | --- |
| `formats::gff`, `text`, `globals` unit tests | GFF writer and reader agree; Windows-1252 both ways; booleans most significant bit first |
| `every_save_round_trips` | every GFF and archive of every save found (10 KotOR 1, 4 KotOR 2) survives write and read unchanged, and the save model opens each |
| `edits_survive_a_write` | on a copy of each of the 14 saves: Strength, a skill, XP, alignment, a feat added, one power removed, credits, an item added, influence (KotOR 2), a global switch flipped and an NPC's Constitution in all copies; written, read back, each change present, Dexterity and time played unchanged, the backup holding the old Strength |
| `a_new_class_brings_its_level_record` | a second class adds one level record, its hit die and a power list |

In the games (the test copy of KotOR 1 and the Steam KotOR 2; the real saves were copied,
never written):

* KotOR 1: a copy of GalaxyMap with the name "Kmrp Tester", Strength 24, Charisma 16,
  Computer Use 14, a feat, a power removed and one added, credits 424,242, two items and an
  NPC's Constitution changed. It loaded; the character screen showed the name, Strength 26
  (24 plus the worn gauntlets' 2), Charisma 16 and Force 112/112 (the game's own
  recalculation from the higher Charisma); the skills screen Computer Use 14; the inventory
  424,242 credits.
* KotOR 2: the same changes on a copy of Game3, in the local `saves` folder (so Steam Cloud
  was not involved; removed afterwards). It loaded; the character screen showed "Kmrp
  Tester", Strength 24, Charisma 16.

The interface was checked at 1600x900 in dark and light mode, KotOR and KotOR II colours,
every tab and the pop-ups, by screenshots.

**Settings** (2026-10-22): the gear at the top right, on the list of saves and in the editor,
opens one pop-up, kept in `settings.txt` in `<data>/KMRP/Save Editor` (`%LOCALAPPDATA%` on
Windows, `~/Library/Application Support` on macOS, `$XDG_DATA_HOME` or `~/.local/share` on Linux):

| Setting | What it does |
| --- | --- |
| Text Size | Small (the first release's sizes), Medium (1.1 times, the default), Large (1.2 times); every text grows, the boxes around names and labels with it |
| Appearance | Dark or Light; it replaced the round moon and sun button at the bottom right, which took a footer's height |
| Game Folders | the KotOR and KotOR II folders in use, each with Change (as KSE's `kse.ini` keeps `K1_Path` and `K2_Path`) |
| Save Folders | the folders added by hand, each with Remove, and Add a Save Folder (KSE's `K1_SavePath`, `K2_SavePath`, `K2_SavePathCloud`; the editor finds the usual ones itself) |

Folders change only from the list of saves: a new game folder can switch the game under an
open save. Edges of buttons and fields were raised to about 3:1 against the field they sit on
(they were about 1.8:1 and hard to see). Checked by screenshots at all three sizes, every tab
at Large. *Corrected 2026-10-22:* Large was first 1.3 times; at that size the Character
tab's labels, the attribute names and the Inventory headings ran into each other, so the
steps are 1.0, 1.1 and 1.2. **Untested**: other window sizes than 1600x900
(the minimum is 1280x780), Linux and macOS, every place in section 2 marked untested,
importing a party member and comparing globals in the game itself, containers and stores in
the game.

To check a save by hand: open it in the editor, change one value, Save Changes; the bottom
bar names the backup folder. Open the save in the game. To undo, copy the backup's files over
the save folder.
