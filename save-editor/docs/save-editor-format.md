# KotOR 1 and KotOR 2 PC savegame format: specification for a Rust save editor

Reference for the [KMRP Save Editor](save-editor.md), following the [documentation standard](../../docs/documentation-standard.md). The lab record of how the editor was checked against the games is in [save-editor.md](save-editor.md), section 8.

Status: research document, 2026-10-22. Written for implementing a new,
cross-platform save editor. Nothing here is derived from the source code of
KSE (KotOR Savegame Editor) or any of its forks.

## 0. Sources and confidence

Every fact is tagged with where it comes from.

| Tag | Meaning |
| --- | --- |
| **[file]** | Measured on real KotOR 1 Steam saves on the maintainer's PC (read only), with a small Python parser written for this document. |
| **[RE]** | From the maintainer's own (private) reverse engineering of the KotOR 1 executable, or from a disassembly of the unpacked KotOR 1 1.03 executable made for this document (label cross references, read and write sites). |
| **[game]** | Measured on the installed KotOR 1 game files (`chitin.key`, `data/*.bif`, `dialog.tlk`). |
| **[doc]** | Public format documentation (BioWare Aurora format documents, xoreos, PyKotor docs, Deadly Stream and community wiki descriptions, Aspyr support pages). |
| **UNCONFIRMED** | Could not be checked against a real file or the engine. Treat as a hypothesis and verify before relying on it. |

KotOR 2 (TSL) is not installed on the research machine. **Everything about
KotOR 2 is from public documentation or by analogy with KotOR 1 and is
UNCONFIRMED unless stated otherwise.**

> **Correction, 2026-10-22, later the same day.** KotOR 2 was installed (Steam, German
> release, TSLRCM 1.8.6) and four real KotOR 2 saves were read. Section 7.0 lists what
> they confirmed and what they corrected; the sentence above described the research
> machine when this document was first written and is kept as it was.

Saves inspected [file] (folder `C:\Program Files (x86)\Steam\steamapps\common\swkotor\saves\`):

| Folder | LASTMODULE | Notes |
| --- | --- | --- |
| `000226 - GalaxyMap` | `ebo_m12aa` (Ebon Hawk) | Main reference save. 18 SAVEGAME entries, 9 nested modules, 7 AVAILNPC files. Party empty (PT_NUM_MEMBERS 0), all recruited NPCs spawned on the Hawk. |
| `000023 - Game22` | `manm26ac` | 2 party members (Bastila, Juhani). Heavily edited character (Str 55, level 20/20). |
| `000134 - Game133` | `tar_m08aa` | 2 party members, an NPC (Canderous) is party leader. |
| `000225 - Game224` | `tat_m17ae` | 2 party members. |

All integers are little endian. "Offset" means byte offset from the start of
the containing file (or of the containing nested resource) unless stated.

---

## 1. Container and resource formats

### 1.1 GFF V3.2 (Generic File Format)

All save data except `Screen.tga` is GFF, either as loose files or inside the
ERF containers.

#### 1.1.1 Header (56 bytes, 0x38) [file][RE]

| Offset | Type | Name | Notes |
| --- | --- | --- | --- |
| 0x00 | char[4] | FileType | e.g. `"UTC "`, `"IFO "`, `"PT  "` (space padded). |
| 0x04 | char[4] | FileVersion | `"V3.2"`. |
| 0x08 | u32 | StructOffset | Always 56 in files the engine writes. |
| 0x0C | u32 | StructCount | Number of 12-byte struct entries. |
| 0x10 | u32 | FieldOffset | |
| 0x14 | u32 | FieldCount | Number of 12-byte field entries. |
| 0x18 | u32 | LabelOffset | |
| 0x1C | u32 | LabelCount | Number of 16-byte labels. |
| 0x20 | u32 | FieldDataOffset | |
| 0x24 | u32 | FieldDataCount | **Size in bytes**. |
| 0x28 | u32 | FieldIndicesOffset | |
| 0x2C | u32 | FieldIndicesCount | **Size in bytes** (4 x number of indices). Measured: savenfo has 15 fields in one struct and FieldIndicesCount 60. |
| 0x30 | u32 | ListIndicesOffset | |
| 0x34 | u32 | ListIndicesCount | **Size in bytes**. |

The engine's writer (WriteGFFData) [RE] computes the offsets sequentially and
writes the sections in this fixed order: header, structs, fields, labels,
field data, field indices, list indices. Every engine-written save GFF
measured follows that order with no padding [file].

**Load-time validation [RE]:** when a GFF resource is serviced, the engine
compares the first dword with the FileType it expects for that resource and
the second with `"V3.2"`; on mismatch the resource is rejected (treated as not
loaded). Section pointers are taken as `base + offset` for every section whose
count is non-zero. No bounds checks against the file size were seen in the
header code, so a bad offset is a crash, not an error message. The writer
always stamps `"V3.2"` whatever version string the caller passes.

#### 1.1.2 Struct array (12 bytes each)

| Offset | Type | Name | Notes |
| --- | --- | --- | --- |
| 0 | u32 | StructID | Type tag chosen by the writer. The top-level struct (index 0) has 0xFFFFFFFF. |
| 4 | u32 | DataOrDataOffset | FieldCount == 1: the field index itself. FieldCount > 1: byte offset into the field-indices block where FieldCount u32 field indices start. FieldCount == 0: the engine writes 0xFFFFFFFF [file] (`CombatRoundData`, struct id 51930, in the Galaxy IFO). |
| 8 | u32 | FieldCount | |

Struct index 0 is always the root.

#### 1.1.3 Field array (12 bytes each)

| Offset | Type | Name | Notes |
| --- | --- | --- | --- |
| 0 | u32 | Type | See 1.1.5. |
| 4 | u32 | LabelIndex | Index into the label array. |
| 8 | u32 | DataOrDataOffset | Simple types: the value itself (low bytes, little endian). Complex types: byte offset into the field-data block. Struct: struct index. List: byte offset into the list-indices block. |

#### 1.1.4 Labels, field indices, list indices

* Label: 16 bytes, ASCII, NUL padded, **not** NUL terminated when exactly 16
  characters long (`PT_PLAYEDSECONDS` is exactly 16 bytes) [file]. Labels are
  unique within a file (the engine de-duplicates: the Galaxy module IFO has
  2096 fields and 274 labels). Label matching is by exact bytes; treat it as
  case sensitive (`willbonus` is lower case while `WillSaveThrow` is not).
* Field indices: a flat u32 array, referenced by multi-field structs.
* List indices: a sequence of records `u32 count, u32 struct_index[count]`.
  A List field's data is the byte offset of its record. An empty list is a
  record with count 0.

#### 1.1.5 Field types

| Id | Name | Storage | Size / layout |
| --- | --- | --- | --- |
| 0 | BYTE | inline | u8 |
| 1 | CHAR | inline | i8 |
| 2 | WORD | inline | u16 |
| 3 | SHORT | inline | i16 |
| 4 | DWORD | inline | u32 |
| 5 | INT | inline | i32 |
| 6 | DWORD64 | field data | u64 |
| 7 | INT64 | field data | i64 |
| 8 | FLOAT | inline | f32 |
| 9 | DOUBLE | field data | f64 |
| 10 | CExoString | field data | u32 length, then bytes (no NUL). Windows-1252 for English data [file]. |
| 11 | ResRef | field data | u8 length (0..16), then bytes. |
| 12 | CExoLocString | field data | see below |
| 13 | VOID | field data | u32 length, then raw bytes |
| 14 | Struct | inline | struct index |
| 15 | List | inline | byte offset into list indices |
| 16 | Orientation | field data | 4 x f32 (quaternion) |
| 17 | Vector | field data | 3 x f32 |
| 18 | StrRef | field data | Defined in later Aurora docs; not used in any KotOR 1 save measured. UNCONFIRMED for KotOR. |

Inline values occupy the low bytes of the 4-byte slot; an editor should write
the unused high bytes as 0 (the engine does) [file].

**CExoLocString layout [file][RE]:**

| Offset | Type | Name |
| --- | --- | --- |
| 0 | u32 | TotalSize: bytes that follow this field (it excludes itself). |
| 4 | i32 | StringRef into dialog.tlk, -1 for none. |
| 8 | u32 | SubStringCount |
| 12.. | | SubStringCount x { i32 StringID, u32 Length, char[Length] } |

`StringID = language * 2 + gender` (gender 0 male/neutral, 1 female); the
reader splits it with signed `/ 2` and `% 2` [RE]. **The reader requires the
substrings to consume TotalSize exactly** (`TotalSize - 8 - sum(8 + Length) ==
0`) and also requires `TotalSize + 4 <= available field data`; otherwise the
read fails and the caller's default is used [RE]. Example [file]: `Mod_Name`
"Ebon Hawk" has TotalSize 25 = 4 + 4 + 4 + 4 + 9. An empty locstring is
TotalSize 8, StrRef -1, count 0.

#### 1.1.6 What a writer must do to be accepted

1. Write FileType exactly as the original (see the table in 2.1) and version `V3.2`.
2. Emit sections in the engine's order with contiguous, unpadded offsets. Not
   strictly required by the reader, but it is the only layout ever observed.
3. Use byte counts for FieldDataCount, FieldIndicesCount and ListIndicesCount.
4. Root struct at index 0 with StructID 0xFFFFFFFF.
5. Single-field structs store the field index directly; zero-field structs
   store 0xFFFFFFFF; never point a single-field struct into the field-indices block.
6. Make every CExoLocString TotalSize exact.
7. Keep labels at most 16 bytes; reuse one label entry per distinct name.
8. Preserve StructIDs from the original (they encode equipment slots and
   object kinds, see 3.6 and 5.1). Preserve field order and types: the engine
   reads by label, but some readers check the type (CExoLocString is checked
   for type 12 [RE]), so never change a field's type.
9. Preserve unknown fields and lists verbatim (round-trip everything).

### 1.2 ERF V1.0 (ERF / MOD / SAV / HAK containers)

`SAVEGAME.sav` and each nested module save inside it are ERF V1.0 containers
whose FileType is **`"MOD "`** (not `"SAV "`) in every KotOR 1 save measured,
both outer and nested [file]. Readers should accept `"ERF "`, `"MOD "`,
`"SAV "`, `"HAK "` with version `"V1.0"`. KotOR 2 SAVEGAME.sav FileType:
UNCONFIRMED (documented as also `"MOD "` by community tools).

#### 1.2.1 Header (160 bytes, 0xA0) [file][RE]

| Offset | Type | Name | Measured in saves |
| --- | --- | --- | --- |
| 0x00 | char[4] | FileType | `"MOD "` |
| 0x04 | char[4] | Version | `"V1.0"` |
| 0x08 | u32 | LanguageCount | 0 |
| 0x0C | u32 | LocalizedStringSize | 0 |
| 0x10 | u32 | EntryCount | 18 (Galaxy), 3 per nested module |
| 0x14 | u32 | OffsetToLocalizedString | 160, but **0** in one save (`000026 - Game25`) when LanguageCount is 0: accept both |
| 0x18 | u32 | OffsetToKeyList | 160 |
| 0x1C | u32 | OffsetToResourceList | 160 + 24 x EntryCount |
| 0x20 | u32 | BuildYear | years since 1900 (114 = 2014, 126 = 2026) |
| 0x24 | u32 | BuildDay | day of year, 0 based |
| 0x28 | u32 | DescriptionStrRef | 0 in saves (0xFFFFFFFF in many shipped ERFs) |
| 0x2C | u8[116] | Reserved | all zero |

The engine's ERF writer fills BuildYear and BuildDay from `localtime(time())`
(`tm_year`, `tm_yday`) when it writes the header [RE]. The values are
informational; nothing seen validates them. (Some saves carry 2014 dates
although written in 2026, so the save writer evidently reuses an older header
in some paths: UNCONFIRMED why.)

#### 1.2.2 Localized string list

LanguageCount records of `{u32 LanguageID, u32 StringSize, char[StringSize]}`.
Empty in saves.

#### 1.2.3 Key list (24 bytes per entry) [file][RE]

| Offset | Type | Name | Notes |
| --- | --- | --- | --- |
| 0 | char[16] | ResRef | NUL padded; case insensitive. Saves use mixed case (`AVAILNPC0`, `INVENTORY`, `REPUTE`, `Module`). |
| 16 | u32 | ResID | Equals the entry index in every save. |
| 20 | u16 | ResType | see 1.2.5 |
| 22 | u16 | Unused | 0 |

#### 1.2.4 Resource list (8 bytes per entry)

`{u32 OffsetToResource, u32 ResourceSize}`, same order as the key list.
Resource data follows the resource list contiguously in key order, unpadded
(Galaxy: first data at 736 = 592 + 18 x 8; nested modules: 256 = 232 + 3 x 8) [file].

#### 1.2.5 Resource type ids relevant to saves

Measured in saves [file] are marked with a check; the rest [doc] (xoreos
resource type table), several confirmed in `chitin.key` [game].

| Id | Ext | Content | Seen |
| --- | --- | --- | --- |
| 0 | res | generic GFF (used for `INVENTORY`) | saves |
| 1 | bmp | | |
| 3 | tga | | key |
| 4 | wav | | key |
| 2002 | mdl | | key |
| 2009 | nss | | key |
| 2010 | ncs | | key |
| 2012 | are | area static data (GFF `ARE `) | saves |
| 2014 | ifo | module info (GFF `IFO `) | saves |
| 2016 | wok | | key |
| 2017 | 2da | | key |
| 2022 | txi | | key |
| 2023 | git | area instance data (GFF `GIT `) | saves |
| 2025 | uti | item template | key |
| 2027 | utc | creature (GFF `UTC `) | saves |
| 2029 | dlg | | key |
| 2030 | itp | | key |
| 2032 | utt | trigger | key |
| 2035 | uts | sound | |
| 2036 | ltr | | key |
| 2037 | gff | | |
| 2038 | fac | faction (GFF `FAC `) | saves (`REPUTE`) |
| 2040 | ute | encounter | key |
| 2042 | utd | door | key |
| 2044 | utp | placeable | key |
| 2047 | gui | | key |
| 2051 | utm | store | |
| 2052 | dwk | | key |
| 2053 | pwk | | key |
| 2056 | jrl | journal | key |
| 2057 | sav | nested module save ERF | saves |
| 2058 | utw | waypoint | key |
| 2060 | ssf | | key |
| 3000 | lyt | | key |
| 3001 | vis | | key |
| 3007 | tpc | | |
| 3008 | mdx | | key |
| 9997 | erf | | |
| 9998 | bif | | |
| 9999 | key | | |

### 1.3 KEY V1 / BIF V1 (reading game resources) [game]

**chitin.key:**

| Offset | Type | Name | Measured |
| --- | --- | --- | --- |
| 0 | char[4] | FileType | `"KEY "` |
| 4 | char[4] | Version | `"V1  "` |
| 8 | u32 | BIFCount | 26 |
| 12 | u32 | KeyCount | 25836 |
| 16 | u32 | OffsetToFileTable | 64 |
| 20 | u32 | OffsetToKeyTable | 847 |
| 24 | u32 | BuildYear | 103 |
| 28 | u32 | BuildDay | 309 |
| 32 | u8[32] | Reserved | |

File table entry (12 bytes): `u32 FileSize, u32 FilenameOffset, u16
FilenameSize, u16 Drives`. Filename is relative with backslashes (e.g.
`data\2da.bif`), NUL terminated within FilenameSize. Convert `\` to the
platform separator; on case-sensitive file systems match case-insensitively.

Key table entry (22 bytes, packed): `char[16] ResRef, u16 ResType, u32 ResID`.
`ResID = (bif_index << 20) | resource_index_in_bif`.

**BIF:** header `"BIFF"`, `"V1  "`, `u32 VariableResourceCount`, `u32
FixedResourceCount` (0), `u32 OffsetToVariableTable` (20). Variable entry (16
bytes): `u32 ID, u32 Offset, u32 FileSize, u32 ResType`. The entry ID equals the
key's ResID [game] (the lower 20 bits index the table).

Resolution order for a resource: `Override\` folder, then module/ERF/RIM
being loaded, then `chitin.key`. (KotOR 2 adds Override subfolders, 7.2.)

### 1.4 2DA V2.b (binary) [game]

| Part | Layout |
| --- | --- |
| Signature | `"2DA V2.b\n"` (9 bytes) |
| Column headers | Tab-terminated labels, the list ends with one NUL byte |
| Row count | u32 |
| Row labels | Row count tab-terminated strings (usually `"0"`, `"1"`, ...) |
| Cell offsets | (rows x columns) u16, row major, each an offset into the cell data |
| Cell data size | u16 |
| Cell data | NUL-terminated strings; identical strings are shared. An empty cell is `""` (displayed as `****` in text 2DA). |

No trailing bytes after the data block [game]. Text 2DA (`2DA V2.0`) in
Override must also be supported (whitespace separated, `****` = empty).

Tables needed by an editor (all present in `2da.bif` [game]):
`classes`, `exptable`, `feat`, `skills`, `spells`, `baseitems`, `appearance`,
`portraits`, `npc` (KotOR 1 PercentXP), `itempropdef`, `iprp_*`, `upgrade`,
`globalcat` (the variable catalogue). Labels resolve through dialog.tlk.

### 1.5 TLK V3.0 [game]

Header (20 bytes): `"TLK "`, `"V3.0"`, `u32 LanguageID` (0 English), `u32
StringCount` (49297), `u32 StringEntriesOffset` (= 20 + 40 x count).

String data entry (40 bytes): `u32 Flags` (1 text present, 2 sound present, 4
sound length present; 7 typical), `char[16] SoundResRef`, `u32 VolumeVariance`,
`u32 PitchVariance`, `u32 OffsetToString` (relative to StringEntriesOffset),
`u32 StringSize`, `f32 SoundLength`. Strings are Windows-1252 for English
(other languages use their code page [doc]). StrRef 0 is "Bad StrRef" [game].

### 1.6 Screen.tga (save thumbnail) [file]

Uncompressed TGA, 18-byte header, no image ID, no colour map, no footer:
`ImageType 2` (true colour), `256 x 256`, `24 bpp`, descriptor 0 (origin
bottom left), BGR pixel order, 196 608 bytes of pixels, file size 196 626.
The game shows it scaled; keeping 256x256x24 is safest.

---

## 2. Save folder layout (KotOR 1, PC)

### 2.1 Files in a save folder [file]

Folder name: `NNNNNN - <name>` (six-digit slot number). Quick save and
autosave use `000000 - QUICKSAVE` and `000001 - AUTOSAVE` [doc]. On the
Steam install the folder is `Saves` (capital S) inside the game folder; it is
case insensitive on Windows.

| File | Format (FileType) | Holds |
| --- | --- | --- |
| `savenfo.res` | GFF `NFO ` | Load-screen summary only (2.2). |
| `PARTYTABLE.res` | GFF `PT  ` | Party state, credits, party XP pool, time played, Pazaak, journal, galaxy map, message logs (2.3). |
| `GLOBALVARS.res` | GFF `GVT ` | Global script variables (section 4). |
| `SAVEGAME.sav` | ERF `MOD ` | Nested module saves, NPC roster creatures, party inventory, factions (2.4). |
| `Screen.tga` | TGA | Thumbnail (1.6). |

There is **no** `PARTYTABLE` or `GLOBALVARS` inside `SAVEGAME.sav` in KotOR 1 [file].

### 2.2 savenfo.res (`NFO `) [file]

| Label | Type | Example | Notes |
| --- | --- | --- | --- |
| AREANAME | CExoString | `Ebon Hawk` | Display name of the current area. |
| LASTMODULE | CExoString | `ebo_m12aa` | Module to resume; must name a nested module save in SAVEGAME.sav. Read by the load-game screen [RE]. |
| TIMEPLAYED | DWORD | 19713 | Seconds; written from the party table's total played seconds [RE]; equals PT_PLAYEDSECONDS [file]. |
| CHEATUSED | BYTE | 0 | Mirrors PT_CHEAT_USED. |
| SAVEGAMENAME | CExoString | `GalaxyMap` | |
| GAMEPLAYHINT | BYTE | 46 | Loading-screen hint index. |
| STORYHINT | BYTE | 30 | |
| LIVE1..LIVE6 | CExoString | `''` | Xbox Live content, unused on PC. |
| LIVECONTENT | BYTE | 0 | |
| PORTRAIT0 | ResRef | `po_pmhc4d2` | Portrait of the party leader (in `Game133` the leader is Canderous and PORTRAIT0 is `po_pcanderous`). |
| PORTRAIT1, PORTRAIT2 | ResRef | `po_pjuhani` | Present only when the party has members (17 fields instead of 15). |

The engine reads TIMEPLAYED, LASTMODULE, AREANAME, SAVEGAMENAME, CHEATUSED and
GAMEPLAYHINT from it only in the load/save GUI code [RE]. Keep it consistent
with PARTYTABLE but treat it as derived data.

### 2.3 PARTYTABLE.res (`PT  `) [file][RE]

Root fields in file order (all observed in KotOR 1 saves):

| Label | Type | Meaning |
| --- | --- | --- |
| PT_GOLD | DWORD | **Party credits** (the creature `Gold` field is 0 for the PC). When an NPC joins, its own Gold is added to the party pool [RE]. |
| PT_XP_POOL | INT | Cumulative party XP awarded. Every XP award adds to it and to each member and the PC [RE] (DistributeExperience). Equals the PC's Experience in the Galaxy save (55480). |
| PT_PLAYEDSECONDS | DWORD | Time played, seconds. |
| PT_CONTROLLED_NP | INT | NPC index the player currently controls, -1 = the PC. |
| PT_SOLOMODE | BYTE | Solo mode. |
| PT_CHEAT_USED | BYTE | Cheat flag. |
| PT_NUM_MEMBERS | BYTE | Active party members (0..2). |
| PT_MEMBERS | List (struct id 0) | `PT_MEMBER_ID` INT (NPC index), `PT_IS_LEADER` BYTE. |
| PT_AVAIL_NPCS | List (9 x struct id 0) | Indexed by NPC index: `PT_NPC_AVAIL` BYTE (recruited), `PT_NPC_SELECT` BYTE (selectable in the party screen). |
| PT_AISTATE | INT | |
| PT_FOLLOWSTATE | INT | |
| GlxyMap | Struct (id 0) | `GlxyMapNumPnts` DWORD (16), `GlxyMapPlntMsk` DWORD (bit mask of unlocked planets), `GlxyMapSelPnt` INT (-1 none). **Added 2026-10-22 [file]:** the mask holds two 16-bit halves and an available planet has bit *i* set in both: Game22 and Game224 read `0b1000_1111_1000_0000_1000_1111_1000` (planetary.2da rows 3 to 7 and 11, Dantooine to Korriban and Yavin, and the same again from bit 19); eight other saves, GalaxyMap among them, read 0. What the upper half means: UNCONFIRMED. |
| PT_PAZAAKCARDS | List (19 x id 0) | `PT_PAZAAKCOUNT` INT per card type: number of Pazaak side cards owned. Entry 18 was stored as BYTE in the Galaxy save, so read the type per element. Card ids 0..17 [RE: the engine maps cards with `(byte + 11) % 18`]. |
| PT_PAZSIDELIST | List (10 x id 0) | `PT_PAZSIDECARD` INT, the chosen side deck, -1 = empty slot. |
| PT_TUT_WND_SHOWN | VOID (6 bytes) | Bit field of tutorial windows already shown. |
| PT_LAST_GUI_PNL | INT | |
| PT_FB_MSG_LIST | List (<= 64) | Combat feedback log: `PT_FB_MSG_MSG` CExoString, `PT_FB_MSG_TYPE` DWORD, `PT_FB_MSG_COLOR` BYTE. Safe to empty. |
| PT_DLG_MSG_LIST | List (<= 64) | Dialogue log: `PT_DLG_MSG_SPKR`, `PT_DLG_MSG_MSG` CExoString. Safe to empty. |
| PT_COST_MULT_LIS | List (92) | `PT_COST_MULT_VAL` FLOAT (store cost multipliers; all 1.0 measured). Meaning of the index: UNCONFIRMED. |
| JNL_SortOrder | INT | Journal sort order. |
| JNL_Entries | List (id 0) | Journal: `JNL_PlotID` CExoString (journal category tag in `global.jrl`), `JNL_State` INT (entry id), `JNL_Date` DWORD, `JNL_Time` DWORD. |

The journal is stored here, not in a `.jrl` file inside the save [file][RE]
(LoadJournal / SaveJournal read and write `JNL_*`).

**KotOR 1 NPC index** (row of `npc.2da` [game], order of AVAILNPCn and PT_AVAIL_NPCS):

| Index | NPC | Tag | PercentXP |
| --- | --- | --- | --- |
| 0 | Bastila | bastila | 80 |
| 1 | Canderous | cand | 80 |
| 2 | Carth | carth | 80 |
| 3 | HK-47 | hk47 | 80 |
| 4 | Jolee | jolee | 80 |
| 5 | Juhani | juhani | 80 |
| 6 | Mission | mission | 80 |
| 7 | T3-M4 | t3m4 | 80 |
| 8 | Zaalbar | zaalbar | 80 |

### 2.4 SAVEGAME.sav contents [file]

Galaxy save, in key order:

| ResRef | Type | Contents |
| --- | --- | --- |
| `AVAILNPC0..8` | 2027 utc (`UTC `) | One creature per **recruited** NPC (missing indices = not recruited; Galaxy has 0,1,2,5,6,7,8 and PT_NPC_AVAIL is 0 for 3 and 4). Written by `CSWPartyTable::AddNPC` / `SaveMember` as `GAMEINPROGRESS:AVAILNPCn` [RE]. |
| `<module>` (e.g. `danm13`, `ebo_m12aa`) | 2057 sav (nested ERF `MOD `) | One per visited module: `<area>.git`, `<area>.are`, `Module.ifo`. |
| `INVENTORY` | 0 res (`INV `) | Party inventory: root `ItemList` (struct id 0 per item, 89 items in Galaxy). Items here carry no `ObjectId`. |
| `REPUTE` | 2038 fac (`FAC `) | Faction table: `FactionList` (`FactionName`, `FactionParentID` DWORD, `FactionGlobal` WORD; struct id = index) and `RepList` (`FactionID1`, `FactionID2`, `FactionRep` DWORD 0..100; struct id = index). |

There is no separate PC `.utc` in a KotOR 1 SAVEGAME.sav [file].

### 2.5 Where each value lives (KotOR 1)

| Value | Location | Notes |
| --- | --- | --- |
| Player creature | `SAVEGAME.sav` > nested `<LASTMODULE>` > `Module.ifo` > `Mod_PlayerList[0]` (struct id **48813 = 0xBEAD**) | The authoritative copy [RE: LoadServerCharacter reads `Mod_PlayerList`]. **Every** nested Module.ifo has its own stale snapshot of the player from when it was last left [file: Galaxy save has player XP 44100..55480 across modules]. Edit the LASTMODULE copy; updating the others is harmless and avoids confusion. |
| Party member creatures | `AVAILNPCn.utc` | Authoritative for members in the active party: they are **not** in the module GIT [file: Game22]. |
| NPCs standing in the current module (Ebon Hawk) | Both `AVAILNPCn.utc` **and** the module `.git` `Creature List` | Measured identical copies in the Galaxy save (all 7 recruited NPCs). Edit both or the change is lost or duplicated depending on which one the game spawns. |
| Party inventory | `INVENTORY.res` `ItemList` | The PC's own `ItemList` is empty; equipped items are in each creature's `Equip_ItemList`. |
| Credits | `PARTYTABLE.res` `PT_GOLD` | |
| Party XP | `PT_XP_POOL` | NPC catch-up base (3.9). |
| Creature XP | each creature's `Experience` | |
| Time played | `PT_PLAYEDSECONDS`, mirrored in savenfo `TIMEPLAYED` | |
| Area name / last module | savenfo `AREANAME`, `LASTMODULE` | |
| Cheat flag | `PT_CHEAT_USED`, savenfo `CHEATUSED` | |
| Pazaak cards | `PT_PAZAAKCARDS`, `PT_PAZSIDELIST` | |
| Journal | `JNL_Entries` | |
| Solo mode | `PT_SOLOMODE` | |
| Galaxy map | `GlxyMap` struct | |
| Global variables | `GLOBALVARS.res` | Section 4. |
| Factions / reputation | `REPUTE.fac` | |
| Area objects | nested `<area>.git` | Section 5. |
| Influence, components, chemicals | KotOR 2 only (7.1) | |

---

## 3. Creature structure (UTC in a save)

Same field set for the player (`Mod_PlayerList` element, plus five `Mod_*`
fields), `AVAILNPCn.utc` roots and GIT `Creature List` elements (struct id 4)
[file]. Field order observed for the player:

### 3.1 Identity and appearance

| Label | Type | Notes |
| --- | --- | --- |
| Mod_CommntyName | CExoString | Player only (`Bad StrRef`). |
| Mod_IsPrimaryPlr | BYTE | Player only, 1. |
| Mod_FirstName, Mod_LastName | CExoLocString | Player only; keep equal to FirstName/LastName. |
| ObjectId | DWORD | Player and GIT creatures; absent in AVAILNPC files. Do not change. |
| FirstName, LastName, Description | CExoLocString | Player name is a substring with StrRef -1. |
| IsPC | BYTE | 1 for the player. Read into the stats object and **switches the max-HP formula** (3.4) [RE]. |
| Tag | CExoString | Empty for the PC, `bastila` etc. for NPCs. |
| Conversation | ResRef | |
| Interruptable | BYTE | |
| Age | INT | |
| Gender | BYTE | 0 male, 1 female (gender.2da). |
| Race | BYTE | racialtypes.2da (6 human, 5 droid measured). |
| Subrace, SubraceIndex, StartingPackage, Deity | | Unused leftovers. |
| PortraitId | WORD | portraits.2da row (PC 26 measured). |
| Appearance_Type | WORD | appearance.2da row (PC 175). |
| Appearance_Head, DuplicatingHead, UseBackupHead, Tail, Wings | BYTE | |
| Phenotype | INT | |
| Color_Skin, Color_Hair, Color_Tattoo1, Color_Tattoo2 | BYTE | |
| SoundSetFile | WORD | soundset.2da |
| GoodEvil | BYTE | Alignment 0..100 (50 neutral). |
| FactionID | WORD | 0 = Player faction. |
| ChallengeRating | FLOAT | |
| MovementRate | BYTE | |
| PM_IsDisguised | BYTE | (PM_Appearance appears when disguised [RE label list].) |

### 3.2 Attributes, saves, defence

| Label | Type | Read on load? [RE] |
| --- | --- | --- |
| Str, Dex, Con, Int, Wis, Cha | BYTE | **Read.** Base scores; item and effect bonuses are applied at run time. |
| NaturalAC | BYTE | Read. |
| willbonus, fortbonus, refbonus | SHORT | Read (permanent extra save bonuses). |
| RefSaveThrow, WillSaveThrow, FortSaveThrow | CHAR | **Not read. Written** from computed values (GetReflexSavingThrow etc.). Editing them has no effect. |
| ArmorClass | SHORT | **Not read.** Written from GetArmorClass. |
| Plot, Min1HP, Disarmable, PartyInteract, NotReorienting, BodyBag | BYTE | Read. Min1HP = cannot drop below 1 HP. |

### 3.3 Classes, levels, force powers

| Label | Type | Notes |
| --- | --- | --- |
| ClassList | List, struct id **2** | 1 or 2 entries. Each: `Class` INT (classes.2da row), `ClassLevel` SHORT. |
| ClassList[i].SpellsPerDayList | List, struct id **17767** (0x4567) | Only on Jedi classes: one element `NumSpellsLeft` BYTE. |
| ClassList[i].KnownList0 | List, struct id **3** | Force powers known through this class: `Spell` WORD (spells.2da row). Only the Jedi class entry has it [file]. |
| MClassLevUpIn | BYTE | Written by the engine (class index used for the last multi-class level-up). |
| LvlStatList | List, struct id 0 | **Player only** (absent from NPC UTCs [file]). One entry per character level, in order. See 3.5. |
| SkillPoints | WORD | Unspent skill points. |
| SkillList | List, struct id 0, **exactly 8** entries | `Rank` BYTE, index = skills.2da row: 0 ComputerUse, 1 Demolitions, 2 Stealth, 3 Awareness, 4 Persuade, 5 Repair, 6 Security, 7 TreatInjury [game]. |
| FeatList | List, struct id **1** (player) | `Feat` WORD (feat.2da row). Order is acquisition order. |
| SpecAbilityList | List, struct id 4 | NPCs / creatures: `Spell` WORD, `SpellFlags` BYTE, `SpellCasterLevel` BYTE (special abilities, e.g. Bastila's Battle Meditation). |

KotOR 1 classes.2da [game] (hit die, force die per level, skill point base):

| Row | Class | hitdie | forcedie | skillpointbase | spellgaintable |
| --- | --- | --- | --- | --- | --- |
| 0 | Soldier | 10 | 0 | 2 | |
| 1 | Scout | 8 | 0 | 6 | |
| 2 | Scoundrel | 6 | 0 | 8 | |
| 3 | Jedi Guardian | 10 | 4 | 2 | JGD |
| 4 | Jedi Consular | 6 | 8 | 2 | JCN |
| 5 | Jedi Sentinel | 8 | 6 | 4 | JSN |
| 6 | Combat Droid | 12 | 0 | 2 | |
| 7 | Expert Droid | 8 | 0 | 4 | |
| 8 | Minion | 10 | 0 | 2 | |

### 3.4 Hit points and force points: what is stored, what is recomputed [RE][file]

| Label | Type | Read on load? | Meaning |
| --- | --- | --- | --- |
| HitPoints | SHORT | **Read** | Base maximum HP (engine member at creature+0xE0). |
| CurrentHitPoints | SHORT | **Read** | Current HP **relative to the base**: saved as `current - (GetMaxHitPoints() - HitPoints)`. |
| MaxHitPoints | SHORT | **Not read** | Written from GetMaxHitPoints(1). Informational. |
| PregameCurrent | SHORT | **Not read** | Written from GetCurrentHitPoints(1). |
| ForcePoints | SHORT | **Read** | Base maximum FP (stats+0x122). |
| CurrentForce | SHORT | **Read** | Saved as `current + ForcePoints - GetMaxForcePoints()`, the same relative scheme. |
| MaxForcePoints | SHORT | **Not read** | Written from GetMaxForcePoints. |

On load: `current_hp = CurrentHitPoints + (GetMaxHitPoints(1) - HitPoints)`
(for creatures with IsPC set) and similarly for force [RE: ReadStatsFromGff,
0x005B1254 to 0x005B135A]. Therefore:

* **Full health:** set `CurrentHitPoints = HitPoints` and `CurrentForce = ForcePoints`
  (Galaxy save: 120/120 with MaxHitPoints 124 is a full-health PC).
* MaxHitPoints and MaxForcePoints can be updated for display but are ignored.
* Negative CurrentHitPoints are legal in files (dead or bleeding members:
  Zaalbar -29 in Game133).

**GetMaxHitPoints [RE] (0x004ED310):**

* Creature with **IsPC = 1** in single player: `max = sum over every character
  level i of max(1, LvlStat[i].LvlStatHitDie + ConMod (+ toughness bonus))`.
  `HitPoints` is not used in that sum. Check on the Galaxy PC: hit dice 2 x 6 +
  9 x 10 = 102, Con modifier +2 (with equipment), 11 levels: 102 + 22 = 124 =
  stored MaxHitPoints.
* Any other creature: `max = HitPoints + level x (ConMod + toughness bonus)`
  (+2 per level with Wookiee Endurance, feat 95), with a floor of 1 per level.
  Check on Bastila: 72 + 9 x 1 = 81 = stored MaxHitPoints.
* Toughness bonus when the flag argument is set (the engine passes 1 when
  saving): +2 per level for feat 124 MASTER_TOUGHNESS, else +1 per level for
  feat 84 TOUGHNESS (not cumulative in this routine).
* `ConMod` is the stats object's current Constitution modifier, including
  item and effect bonuses.

**Consequence:** for the PC, changing max HP means editing the
`LvlStatHitDie` values (and keeping `HitPoints` plausible); for NPCs, edit
`HitPoints`. The per-level loop indexes the level-stat array for every
character level, so **a PC whose total class level exceeds the number of
`LvlStatList` entries is likely to crash** when max HP is computed (the code
dereferences the entry without a null check): derived from the code, not
tested.

How the stored base `HitPoints` of the PC is built at level-up is not fully
explained by the data (Galaxy: HitPoints 120 vs hit dice sum 102): UNCONFIRMED.
Public documentation states KotOR gives the maximum hit die every level (no
roll); the data agrees (every LvlStatHitDie equals the class hit die).

Force points: GetMaxForcePoints (0x004FD490) was not reconstructed; public
documentation and the data (`LvlStatForce` 4 = Jedi Guardian forcedie) say
max FP grows by the class `forcedie` per Jedi level plus a Wisdom/Charisma
bonus. Formula details: UNCONFIRMED.

### 3.5 LvlStatList entries (player only) [file][RE]

| Label | Type | Meaning |
| --- | --- | --- |
| LvlStatHitDie | BYTE | HP gained that level (used by GetMaxHitPoints). |
| LvlStatForce | BYTE | FP gained that level. |
| LvlStatClass | BYTE | Class taken that level. |
| LvlStatAbility | BYTE | Ability raised that level (only on ability levels: 2 of 11 entries in Galaxy). |
| SkillPoints | WORD | |
| SkillList | List of 8 `Rank` BYTE | Ranks added that level. |
| FeatList | List (struct id 0) of `Feat` WORD | Feats gained that level. |
| KnownList0 | List (struct id 0) of `Spell` WORD | Force powers gained that level (Jedi levels). |

When raising the PC's level in an editor, append one consistent LvlStatList
entry per added level (hit die from classes.2da `hitdie`, force from
`forcedie`, class id, empty skill/feat/power lists) and update
`ClassList[].ClassLevel`. Lowering a level should drop the last entries and
anything they granted.

### 3.6 Experience and levelling [game][RE]

* `Experience` DWORD, read on load [RE].
* exptable.2da [game]: level N needs `1000 x N x (N-1) / 2` XP: L2 1000, L3
  3000, L5 10000, L10 45000, L11 55000, L20 190000; row 21 is 0xFFFFFFFF
  (cap at 20). The NPC-join code computes the same thresholds inline [RE].
* XP above the next threshold is legal: the game offers level-up (the level-up
  button and the party screen indicator) and lets the player take the levels
  one at a time. For party NPCs an option bit triggers AutoLevelUp when they
  receive XP and CanLevelUp is true [RE: DistributeExperience, SpawnNPC].
* Setting XP lower than the current level's threshold does not remove levels;
  avoid it.

### 3.7 NPC XP catch-up [RE]

When an NPC is added (`AddNPC`) the engine stores in the creature member
behind `JoiningXP` (INT, read on load) `max(0, threshold(level) - PT_XP_POOL x
PercentXP / 100)`. When the NPC is spawned into the party (`SpawnNPC`), if
`Experience - JoiningXP < PT_XP_POOL x PercentXP / 100` the NPC receives XP to
catch up, and may auto-level. Galaxy save: every NPC has 44384 = 55480 x 80%.
Editing `PT_XP_POOL` therefore raises NPC XP the next time they join; editing
only the PC's Experience does not.

### 3.8 Inventory and equipment [file][RE]

| Label | Type | Notes |
| --- | --- | --- |
| Gold | DWORD | Read; 0 for party creatures (credits live in PT_GOLD). |
| Equip_ItemList | List | **Struct id = equipment slot bit**: 0x1 head, 0x2 body (armour), 0x8 hands (gloves), 0x10 right weapon, 0x20 left weapon, 0x80 left arm, 0x100 right arm, 0x200 implant, 0x400 belt; creature-only slots above (claws, hide) [doc] for 0x4000 and up. Measured PC: 1, 2, 8, 16, 32, 128, 256, 1024. The struct id **is** the slot; one item per slot. |
| ItemList | List | Creature's own inventory: empty for party creatures (party inventory is INVENTORY.res). Struct id 0 for inventory and placeables [file]. |

**Item struct fields** (equipped item; INVENTORY items lack `ObjectId`):

| Label | Type | Read on load? [RE] | Notes |
| --- | --- | --- | --- |
| ObjectId | DWORD | | Only on equipped and placed items. |
| BaseItem | INT | read | baseitems.2da row. |
| Tag | CExoString | read | Template tag, usually equals the UTI ResRef. |
| Identified | BYTE | read | |
| Description, DescIdentified, LocalizedName | CExoLocString | read | |
| StackSize | WORD | read | Must not exceed baseitems.2da `stacking` for the base item. |
| Stolen | BYTE | read | |
| Upgrades | DWORD | read | KotOR 1 upgrade bit mask (upgrade.2da). |
| Dropable, Pickpocketable | BYTE | read | |
| ModelVariation | BYTE | read | |
| Charges, MaxCharges | BYTE | read | |
| Cost | DWORD | **not read** | Written from GetCost (recomputed). |
| AddCost | DWORD | read | |
| Plot | BYTE | read | |
| PropertiesList | List, struct id = index | read | `PropertyName` WORD (itempropdef.2da), `Subtype` WORD, `CostTable` BYTE, `CostValue` WORD, `Param1` BYTE, `Param1Value` BYTE, `ChanceAppear` BYTE (100), `UsesPerDay` BYTE (255), `Useable` BYTE, `UpgradeType` BYTE (255 none). |
| XPosition..ZPosition, XOrientation..ZOrientation | FLOAT | | 0,0,0 and 1,0,0 in inventories. |
| NonEquippable, NewItem, DELETING | BYTE | read | NewItem shows the "new" marker. |

To add an item, the simplest correct approach is to copy the UTI template from
the game (BIF or Override), convert it to this layout (template fields such as
`TemplateResRef`, `Comment`, `PaletteID` are not part of the saved item) and
append it.

### 3.9 Position and runtime state

| Label | Type | Notes |
| --- | --- | --- |
| XPosition, YPosition, ZPosition | FLOAT | Read on load. Moving a creature off the walkmesh: the engine tests and corrects party spawn positions (`AreaTestLocation` / safe location search within 20 m [RE]) for NPC spawns; the PC's own correction: UNCONFIRMED. |
| XOrientation, YOrientation, ZOrientation | FLOAT | Facing as a unit vector (Z 0). |
| AreaId | DWORD | Object id of the area. |
| JoiningXP | INT | See 3.7. |
| FollowInfo | Struct (id 0) | Follow AI state (`FollowObject`, `FollowLocation` Vector...). |
| EffectList | List (struct id 2) | Active effects: `Id` DWORD64, `Type` WORD, `SubType` WORD, `Duration` FLOAT, `SkipOnLoad` BYTE, `ExpireDay`, `ExpireTime`, `CreatorId` DWORD, `SpellId` DWORD, `IsExposed` INT, `NumIntegers` INT, `IntList` (id 3, `Value` INT x8), `FloatList` (id 4), `StringList` (id 5), `ObjectList` (id 6). Equipment bonuses are effects created by the items: do not hand-edit; removing an item's effect without the item (or the reverse) desynchronises stats. |
| CombatInfo | Struct id **51882** (0xCAAA) | Cached combat values (NumAttacks, OnHandAttackMod...). Recomputed. |
| CombatRoundData | Struct id **51930** (0xCADA) | Empty in saves. |
| PerceptionList, ExpressionList (id 5), ActionList, VarTable, SWVarTable | | Leave untouched. `SWVarTable` = `BitArray` (3 x DWORD `Variable`) and `ByteArray` (8 x BYTE `Variable`): the per-object local booleans and numbers used by scripts. |
| DetectMode, StealthMode, CreatureSize, IsDestroyable, IsRaiseable, DeadSelectable, Script* ResRefs, AmbientAnimState, Animation, CreatnScrptFird, Listening, Commandable | | Preserve. |

---

## 4. GLOBALVARS.res (`GVT `) [file][RE]

Root fields (Galaxy save):

| Label | Type | Galaxy | Notes |
| --- | --- | --- | --- |
| CatBoolean | List (id 0) | 809 | Each element: `Name` CExoString. |
| CatNumber | List (id 0) | 369 | |
| CatLocation | List (id 0) | 5 | |
| CatString | List (id 0) | 2 | |
| ValBoolean | VOID | 102 bytes | Bit packed (below). |
| ValNumber | VOID | 369 bytes | One byte per number. |
| ValLocation | VOID | 2400 bytes | Fixed size. |
| ValString | List (id 0) | 2 | Each element: `String` CExoString. |

Packing, exactly as the engine reads and writes it [RE: 0x0052A280 read with
catalogue, 0x005299B0 writer]:

* **Boolean i** (i = index in CatBoolean) is bit `7 - (i % 8)` of byte `i / 8`
  of ValBoolean: **most significant bit first**. The writer emits
  `count / 8 + 1` bytes (809 -> 102; note: a multiple of 8 still gets one
  extra byte). The reader copies at most 113 bytes (0x71), i.e. **904
  booleans maximum**.
* **Number i** is byte i of ValNumber. The VOID length equals the number count.
  Maximum **500** numbers. Storage is one byte; script semantics are signed
  (-128..127) per the KotOR 1 script documentation [doc], UNCONFIRMED in the
  engine. An editor should present it as signed and preserve the raw byte.
* **Location i** is 24 bytes at offset `24 x i` of ValLocation: position
  `f32 x, y, z`, then facing `f32 x, y, z` (unit vector). ValLocation is
  always 2400 bytes = **100** location slots; unused slots are zero position
  with facing (1, 0, 0) [file].
* **String i** is element i of ValString. Maximum **5** strings.
* Names are matched by the catalogue on load (variables missing from the
  file are added; a file without `CatBoolean` is read positionally against
  the engine's built-in table) [RE]. Never reorder a Cat list without
  reordering its values.
* Variable names come from `globalcat.2da`; adding a variable that is not in
  globalcat is accepted by the loader up to the caps, but scripts only read
  names they know.

---

## 5. Area state in a module save

Nested module ERF (`<module>.sav`) holds `<area>.git` (GFF `GIT `),
`<area>.are` (GFF `ARE `) and `Module.ifo` (GFF `IFO `) [file]. The `.are`
is the static area description (copied), the `.git` the live object state.

### 5.1 GIT root [file]

| Label | Type / struct id | Content |
| --- | --- | --- |
| VarTable, SWVarTable | | Area locals. |
| CurrentWeather, WeatherStarted, TransPending, TransPendNextID, TransPendCurrID | BYTE | |
| Creature List | List, id **4** | Creatures (UTC layout, section 3). |
| List | List | (empty) |
| Door List | List, id **8** | Doors. |
| TriggerList | List, id 1 | |
| Encounter List | List | |
| WaypointList | List, id 5 | |
| SoundList | List, id 6 | |
| Placeable List | List, id **9** | Placeables, containers. |
| StoreList | List, id **11** | Merchants. |
| AreaEffectList | List | |
| AreaProperties | Struct id 100 | Music etc. |
| AreaMap | Struct id 101 | Explored-map data (`AreaMapResX/Y`, `AreaMapDataSize`, data VOID). |
| CameraList | List, id 14 | |

### 5.2 Doors (Door List, struct id 8) [file]

Fields relevant to editing:

| Label | Type | Notes |
| --- | --- | --- |
| Tag | CExoString | Identify doors by tag (+ position). |
| OpenState | BYTE | 0 closed, 1 open (2 open the other way [doc]). |
| Locked | BYTE | 1 locked. |
| Lockable | BYTE | |
| KeyRequired | BYTE | 1 = only the key opens it (Security cannot). |
| KeyName | CExoString | Key item tag. |
| OpenLockDC, CloseLockDC | BYTE | Security DC. |
| Plot | BYTE | Indestructible. |
| HP, CurrentHP, Hardness, Fort, Will, Ref | | Bashing. |
| TrapType, TrapFlag, TrapDetectable, TrapDisarmable, DisarmDC, TrapDetectDC, TrapOneShot | | |
| LinkedTo, LinkedToModule, LinkedToFlags, TransitionDestin | | Area transitions. |
| X, Y, Z, Bearing | FLOAT | |
| Static, GenericType, Appearance, PortraitId, Faction | | |
| On* scripts, EffectList, VarTable, SWVarTable, ActionList, Commandable | | Preserve. |

Unlocking a door: `Locked = 0`. Opening: `OpenState = 1` (the area model
state follows on load: UNCONFIRMED whether the walkmesh is updated without the
open animation having run; safer to only unlock). Doors guarded by plot
scripts may be relocked by `OnHeartbeat` or area scripts.

### 5.3 Placeables and containers (struct id 9) [file]

Key fields: `Tag`, `HasInventory`, `ItemList` (items, struct id 0, item
layout of 3.8 with `ObjectId`), `Locked`, `Lockable`, `KeyRequired`,
`KeyName`, `OpenLockDC`, `Open`, `Useable`, `Plot`, `GroundPile`,
`IsBodyBag`, `IsBodyBagVisible`, `IsCorpse`, `DieWhenEmpty`, `X`/`Y`/`Z`/`Bearing`,
`HP`/`CurrentHP`, trap fields, scripts. Containers whose contents are
generated on first open (`OnOpen` / `OnInvDisturbed` scripts with treasure
tables) may still be empty in the save until opened.

New items placed in a container need a unique `ObjectId`: use a value above
every id in the module and keep `Mod_NextObjId0` in `Module.ifo` greater than
it (Galaxy: `Mod_NextObjId0` 383). Object id allocation rules: UNCONFIRMED;
that is the safest approach.

### 5.4 Stores (StoreList, struct id 11) [file]

`Tag`, `LocName`, `MarkDown` INT, `MarkUp` INT, `OnOpenStore`,
`BuySellFlag` BYTE, `ItemList` whose **struct id = item index** (0, 1, 2,
...), each item with an extra `Infinite` BYTE (unlimited stock) before
`BaseItem`.

### 5.5 Module.ifo in a save [file]

`Mod_IsSaveGame` 1, `Mod_Entry_Area`, `Mod_Entry_X/Y/Z`, `Mod_Entry_Dir_X/Y`,
time fields (`Mod_StartYear`... `Mod_PauseDay`, `Mod_PauseTime`),
`Mod_XPScale`, `Mod_NextCharId0/1`, `Mod_NextObjId0/1`,
`Mod_Effect_NxtId` DWORD64, `Mod_Area_list` (struct id 6: `Area_Name`,
`ObjectId`), `Mod_Tokens`, `VarTable`, `SWVarTable` (module-level locals),
`EventQueue`, `Mod_PlayerList` (struct id 48813). `Mod_ID` is a 32-byte VOID.

### 5.2 Spawning: how a saved area's creatures load [RE][file]

From the maintainer's own private reverse engineering of KotOR 1 1.0.3 (addresses below),
checked on real saves of both games on 2026-10-22. KotOR 2's code was **not** read; its
saves have the same fields and its program the same field names, so the same logic is
assumed.

| Fact | Evidence |
| --- | --- |
| A saved `.git` has no `UseTemplates`; the shipped module's does (1), with creatures as `TemplateResRef` plus position only | K1 Game87 against `tar_m03af.rim` |
| The GIT loader `0x0050DD80` reads `UseTemplates` (default 0) and calls the creature loader `0x00504A70`: with templates, a new creature from `TemplateResRef` (`0x005026D0`); without, `ObjectId` (default `0x7F000000`) and the full saved creature (`0x00500350`). Both then read the position, find the nearest walkable point within 20 m (`0x004BE860`, a guess from its arguments) and add it to the area | decompile |
| `Module.ifo` is loaded first (`0x004C9050`) and sets the object counter from `Mod_NextObjId0`; in every save read it is the highest id used plus 1 (K1 Game26 301, K2 Game3 939) | decompile, three saves |
| An `ObjectId` of `0x7F000000` (or none) gets a fresh id from the counter; any other is kept and the counter moves past it. An id already in use moves the *existing* object to a new id, so an id must never be reused | `0x004CFCB0`, `0x004D80E0`, `0x004D7E90` |
| Saved and template creatures go through the same stats reader (`0x005AFCE0`); it fails only for a bad race or perception lookup or a missing or empty `ClassList`. Every save-only field (perception, actions, effects, combat round, local variables) is optional | decompile |
| `CreatnScrptFird` is the "spawn script fired" flag (creature +0x34C). Absent on a save load means fired. At 0, the creature's first AI update runs its `ScriptSpawn` in the game's own script VM, then a heartbeat and a perception pass, and sets it to 1 (`0x004EB6E0`). Nothing runs OnSpawn at load, not even for template creatures or script `CreateObject` | assembly `0x00500525` to `0x00500552`, `0x004EB6E0` |
| Items: a full item struct with no `ObjectId` gets a fresh one; one whose id belongs to another object is dropped; `EquippedRes` / `InventoryRes` entries load their .uti | `0x004FFDA0`, `0x00560970` |

What the editor writes (`src/area.rs`, `Save::spawn_creature`): a new creature is the .utc's
fields without `TemplateResRef`, `Comment`, `PaletteID` and `TemplateList`, struct id 4, with
`CreatnScrptFird` 0, `CreatureSize` 0 (the game takes it from appearance.2da), the defaults
above for the other save-only fields, `AreaId` and the kinds of the fields from a creature
already in the area, and empty perception, action, effect and expression lists. A copy is
the area's creature with those lists empty and `FollowInfo`, `CombatRoundData` and
`CombatInfo` removed; its spawn script has already run, so it keeps its state. Each gets an
`ObjectId` from `Mod_NextObjId0`, as does each full item it carries.

---

## 6. Save locations by platform

| Platform / edition | Path | Confidence |
| --- | --- | --- |
| **K1 Windows Steam** | `<Steam>\steamapps\common\swkotor\Saves\` | Confirmed [file]. |
| K1 Steam Cloud | Steam **Auto-Cloud** syncs that same folder: `userdata\<accountid>\32370\remotecache.vdf` lists `Saves/<folder>/<file>` with `"root" "1"` (the game install dir) and a SHA-1 per file. **No `remote\` copy exists** on this machine; `Saves\steam_autocloud.vdf` names the account id. | Confirmed [file]. |
| K1 Windows retail CD | `C:\Program Files\LucasArts\SWKotOR\saves\`; with UAC and a Program Files install, writes are redirected to `%LOCALAPPDATA%\VirtualStore\Program Files (x86)\LucasArts\SWKotOR\saves\` (or `Program Files` on 32-bit Windows). Check both and prefer the VirtualStore copy when present. | High [doc]. |
| K1 GOG | `<GOG install>\saves\` (default `C:\GOG Games\Star Wars - KotOR\saves\`; newer Galaxy installs under `C:\Program Files (x86)\GOG Galaxy\Games\...`). VirtualStore applies if installed under Program Files. | Medium [doc]. |
| K1 macOS (Aspyr, Steam) | `~/Library/Application Support/Knights of the Old Republic/saves/` | Medium [doc: Aspyr Mac FAQ]. |
| K1 macOS (Mac App Store) | `~/Library/Containers/com.aspyr.kotor/Data/Library/Application Support/KOTOR/saves/` | Medium [doc: Aspyr Mac FAQ]. |
| K1 Linux | No native K1 port; Wine/Proton: Steam game folder as Windows (Proton prefix `steamapps/compatdata/32370/pfx/` only matters for VirtualStore-style redirects, normally unused). | Medium. |
| **K2 Windows Steam (Aspyr 2015 update and later)** | Local: `<Steam>\steamapps\common\Knights of the Old Republic II\saves\`. Cloud saves: `<same>\cloudsaves\<SteamID64>\` inside the game folder, synced through Steam Cloud (app 208580). The in-game save menu switches between local and cloud. | Medium [doc: Steam forums, save-editor setup guides mention a separate cloud save path]. UNCONFIRMED exact folder name. |
| K2 Steam Cloud backing store | `<Steam>\userdata\<accountid>\208580\remote\` (Steam Cloud API storage). | Low, UNCONFIRMED. |
| K2 Windows retail / pre-2015 | `C:\Program Files\LucasArts\SWKotOR2\Saves\` or VirtualStore `%LOCALAPPDATA%\VirtualStore\Program Files (x86)\LucasArts\SWKotOR2\Saves\` | High [doc]. |
| K2 GOG | `<GOG install>\saves\` | Medium. |
| K2 Linux (Aspyr) | `~/.local/share/aspyr-media/kotor2/saves/` (the config `swkotor2.ini` is documented in `~/.local/share/aspyr-media/kotor2/`; saves beside it is an inference). Native Linux build expects **lower-case** file names. | Low, UNCONFIRMED. |
| K2 macOS (Aspyr) | `~/Library/Application Support/Star Wars Knights of the Old Republic II/saves/` or under an `Aspyr` folder | Low, UNCONFIRMED. |
| Android (Aspyr, K1 `com.aspyr.swkotor`, K2 `com.aspyr.swkotor2`) | `/sdcard/Android/data/<package>/files/saves/` (app-private on Android 11+; needs adb or a file manager with access) | Low, UNCONFIRMED. |
| iOS / iPadOS (Aspyr) | Inside the app container `Documents/saves` (or `Library/Application Support/...`); reachable only through Finder file sharing if enabled, or a backup extractor | Low, UNCONFIRMED. |
| Nintendo Switch (Aspyr, 2022) | Console save data; extraction needs homebrew save managers (JKSV, Checkpoint). Folder layout reportedly mirrors PC saves. Any extra compression or wrapper: **not publicly documented**. | Low, UNCONFIRMED. |
| Original Xbox (2003/2004) | Xbox hard disk `UDATA\<TitleID>\<save id>\` with `SaveMeta.xbx` and `SaveImage.xbx`; the save files are signed (HMAC-SHA1 "XCalcSig" with the title's signature key, plus per-console key for non-roamable data). Edited saves fail the signature check and are reported as damaged. Re-signing is publicly documented in Xbox homebrew tools that carry per-title keys; a KotOR-specific key and exactly which files are signed: UNCONFIRMED. | Low. |

Steam Cloud caution: after an offline edit, Steam compares the local files
with `remotecache.vdf` at the next launch. A changed local file with an
unchanged remote normally uploads silently; if the cloud copy also changed
Steam shows a conflict dialog. An editor should warn the user to close the
game and, for K2 cloud saves, edit the folder the game is actually using.

---

## 7. KotOR 2 differences (public documentation; UNCONFIRMED unless noted)

### 7.0 Confirmed on real KotOR 2 saves (2026-10-22) [file]

Read from four Steam Cloud saves of the German Steam release with TSLRCM 1.8.6
(`cloudsaves\<account>\000001 - AUTOSAVE` to `000004 - Game3`), and one written by
the editor and loaded in the game:

| Fact | Measured |
| --- | --- |
| Cloud folder | `<game>\cloudsaves\73340463\`: the Steam **account id** (as in `steam_autocloud.vdf`), not a SteamID64. A local `saves\` folder does not exist until a local save is made; the Load screen has a switch between local and cloud ("Cloud-Speicher"). |
| SAVEGAME.sav | ERF `MOD `, names in lower case: nested module saves, `availnpc0`, `availnpc6`, `availnpc8`, `inventory` (type 0), **`pc` (2027 utc)**, `repute`. So KotOR 2 does keep a `PC.utc` beside `Mod_PlayerList`; the editor changes both. |
| savenfo.res | adds `TIMESTAMP` DWORD64, `PCNAME` CExoString, `SAVENUMBER` DWORD, `STORYHINT0..9` BYTE. `CHEATUSED` read 2 while `PT_CHEAT_USED` read 0 in Game3. |
| PARTYTABLE.res | adds `PT_PCNAME`, `PT_ITEM_COMPONEN` DWORD, `PT_ITEM_CHEMICAL` DWORD (the 16-character labels), `PT_SWOOP1..3`, `PT_NUM_PUPPETS`, `PT_PUPPETS`, `PT_AVAIL_PUPS`, `PT_COM_MSG_LIST`. |
| Influence | `PT_INFLUENCE`: 12 entries of `PT_NPC_INFLUENCE` INT; **-1 for someone not met yet** (Game3: Atton 50, Bao-Dur -1). |
| NPCs | `PT_AVAIL_NPCS` has 12 entries, in the order of section 7.1. |
| Pazaak | `PT_PAZAAKCARDS` has 24 entries (KotOR 1: 19). |
| Writing | A save the editor wrote (name, Strength 24, Charisma 16, credits, a feat, a power removed, two items) loaded in the game, which showed every change on its character screen. |

### 7.1 Save contents

* Same containers: savenfo.res, PARTYTABLE.res, GLOBALVARS.res, SAVEGAME.sav,
  Screen.tga. K2 savenfo adds fields such as `PCNAME` (player name for the load
  list) [doc].
* **NPC indices** (12): 0 Atton, 1 Bao-Dur, 2 Mandalore, 3 G0-T0, 4
  Handmaiden, 5 HK-47, 6 Kreia, 7 Mira, 8 T3-M4, 9 Visas Marr, 10 Hanharr,
  11 Disciple. `PT_AVAIL_NPCS` has 12 elements; `AVAILNPC0..11.utc` [doc].
  Handmaiden/Disciple and Mira/Hanharr are mutually exclusive by story.
* **Influence:** `PARTYTABLE.res` list `PT_INFLUENCE`, one element per NPC
  index with `PT_NPC_INFLUENCE` INT (0..100, 50 neutral) [doc].
* **Components / chemicals** (crafting currencies): PARTYTABLE root INT/DWORD
  fields documented as `PT_ITEM_COMPONEN` and `PT_ITEM_CHEMICAL` (GFF labels
  are limited to 16 characters, so "COMPONENT" is truncated). Verify on a real
  K2 save before writing.
* Pazaak, journal, galaxy map and XP pool follow the K1 names, with
  additional K2 fields (e.g. swoop records, `PT_PCNAME`?) to preserve.
* GLOBALVARS: same Cat/Val layout; K2 has many more variables; caps (904
  booleans etc.) are K1 values from the engine and may differ in K2.
* The PC: also in `Mod_PlayerList` of the LASTMODULE IFO; some documentation
  mentions an additional `PC.utc` in SAVEGAME.sav. KotOR 1 writes
  `GAMEINPROGRESS:PC` when switching the player character [RE], but no `PC`
  entry was found in any K1 SAVEGAME.sav [file]. Check K2 files.
* Creature GFF adds K2 fields (e.g. `SkillList` keeps 8 skills, but K2 items
  have `UpgradeSlot0..5` ResRefs and `UpgradeLevel` instead of the K1
  `Upgrades` mask; creatures have extra fields such as `BonusForcePoints`).
  Treat unknown fields as opaque.

### 7.2 Engine and install differences

* **Classes** (classes.2da, K2) [doc]: 0 Soldier, 1 Scout, 2 Scoundrel, 3 Jedi
  Guardian, 4 Jedi Consular, 5 Jedi Sentinel, 6 Combat Droid, 7 Expert Droid,
  8 Minion, 9 Tech Specialist, 10 Bounty Hunter, 11 Jedi Weapon Master, 12
  Jedi Master, 13 Jedi Watchman, 14 Sith Marauder, 15 Sith Lord, 16 Sith
  Assassin. Prestige classes require level and story conditions; still at
  most 2 classes per creature. Always read the installed classes.2da.
* Max level 50 in exptable (K2) [doc]; read the installed exptable.2da.
* **Override subfolders:** the K2 Aspyr build also loads files from
  subfolders of `Override\` [doc]; resolution order among subfolders:
  UNCONFIRMED.
* **Steam Workshop:** mods subscribed through Steam live in
  `<Steam>\steamapps\workshop\content\208580\<item id>\` and are loaded by the
  K2 Aspyr build in addition to Override [doc]; a save editor reading 2DAs
  should look there too.
* K2 (Aspyr) saves are created by a 64-bit-era port on Mac/Linux with
  lower-case file names; keep the original file name case when writing.

---

## 8. Known pitfalls

| Pitfall | Why | Avoid by |
| --- | --- | --- |
| Removing a force power or feat by rewriting the whole list | The lists are order-preserving and also mirrored in `LvlStatList[].FeatList / KnownList0` (PC). Prerequisite chains (feat.2da `prereqfeat1/2`, spells.2da `prerequisites`) make lone higher tiers inconsistent. | Remove only the selected element; also remove it from the LvlStat entry that granted it; keep prerequisites. |
| Wrong list counts | The reader trusts the u32 count in the list-indices block. | Rebuild list records from the in-memory tree, never patch counts by hand. |
| Inexact CExoLocString TotalSize | The read fails silently and the default is used (names vanish). | Compute TotalSize from the substrings. |
| GFF type or version mismatch | Resource rejected on load. | Keep the 4CC; write V3.2. |
| Item StackSize above baseitems.2da `stacking` | Undefined behaviour in the UI; splitting stacks misbehaves. | Clamp to `stacking` (1 for non-stackables). |
| Equip_ItemList struct id not a valid slot, or an item in a slot its base item does not allow (baseitems `equipableslots` mask) | The struct id is the slot. | Validate against `equipableslots`; one item per slot. |
| More than 2 classes, or a third class added | The engine supports two class slots. | Cap ClassList at 2; Jedi class must be the second for a multiclass PC. |
| Droids with Jedi classes, feats or force powers they cannot use | Droid classes (6, 7) and droid races cannot use force powers; feat.2da / skills.2da `droidcanuse` columns. | Filter by class and race. |
| PC total level larger than LvlStatList length | GetMaxHitPoints indexes one entry per level (3.4). | Add LvlStat entries when adding levels. |
| Editing MaxHitPoints / ArmorClass / saving throws / Cost | Not read on load; recomputed. | Edit the inputs (HitPoints, LvlStatHitDie, Con, items). |
| CurrentHitPoints above HitPoints | Stored value is relative to the base; values above base overheal after the bonus is added. | Full heal = `CurrentHitPoints = HitPoints`. |
| Editing only one copy of an NPC | NPCs can exist in AVAILNPCn and in the current GIT (Ebon Hawk). | Edit both copies. |
| Editing a stale player copy | Every module IFO holds a player snapshot. | Edit the LASTMODULE copy (and optionally all). |
| PT_NUM_MEMBERS out of sync with PT_MEMBERS, members that are not recruited (PT_NPC_AVAIL 0) or without an AVAILNPC file | Party table holds indices only. | Validate the three together; max 2 members, no duplicates. |
| Adding an NPC to PT_AVAIL_NPCS without its AVAILNPCn.utc | Spawning loads `GAMEINPROGRESS:AVAILNPCn`. | Create the UTC from the game's NPC template when recruiting through the editor (UNCONFIRMED which template the game uses; story scripts normally do this). |
| GLOBALVARS over the caps (904 booleans, 500 numbers, 100 locations, 5 strings) | Reader buffers are fixed. | Enforce caps. |
| Reordering Cat lists | Values are positional. | Edit values in place. |
| Duplicate or reused ObjectIds | Object lookups go by id. | Allocate new ids above Mod_NextObjId0 and bump it. |
| Effects left by removed items | Item bonuses live in EffectList with CreatorId = item ObjectId. | When removing an equipped item, also remove effects whose CreatorId is that item, or unequip in game. UNCONFIRMED whether the engine cleans them on load. |
| Text encoding | Names are Windows-1252 (English). | Encode to the TLK language code page; reject characters outside it. |
| Steam Cloud overwriting the edit | Cloud copy newer. | Close the game and Steam sync before editing; tell the user. |

---

## 9. Editor implications (recommendations)

1. **Lossless GFF and ERF core.** Parse into a tree that keeps field order,
   types, struct ids, labels and unknown fields, and writes back in the
   engine's section order. Unit-test: parse and re-serialise every resource of
   the four saves above byte for byte (the engine's own output is
   deterministic: structs in creation order, label table de-duplicated,
   field data in field order). Byte identity is a strong regression test even
   though the game does not require it.
2. **Never modify in place on disk.** Read the whole save folder, build the
   new files in memory, write to a temporary folder, then replace atomically,
   keeping a timestamped backup of the original folder.
3. **Treat derived fields as derived.** Do not offer MaxHitPoints,
   MaxForcePoints, PregameCurrent, saving throws, ArmorClass, item Cost or
   CombatInfo as editable; recompute them for display only (using the
   formulas in 3.4 where known).
4. **Model the duplicated data explicitly**: PC in the LASTMODULE IFO (plus
   stale copies), NPCs in AVAILNPCn plus the current GIT, time and cheat flags
   in both savenfo and PARTYTABLE, party-leader portraits in savenfo. One edit
   in the UI should update every copy.
5. **Level editing as an operation, not a number.** Changing a level should
   add or remove LvlStatList entries (PC), ClassLevel, skill points, and keep
   Experience at least at the new level's threshold. Prefer "set XP and let the
   game level up" as the default, which the engine handles natively.
6. **Drive every choice list from the installed game data** (KEY/BIF,
   Override, and for K2 Override subfolders and Workshop): classes, feats,
   powers, skills, base items, appearances, portraits, globalcat, with names
   from dialog.tlk. Do not hard-code K1 tables for K2.
7. **Validate before writing:** class count <= 2, droid restrictions, stack
   sizes, slot masks, party table consistency, GLOBALVARS caps, unique object
   ids, LocString sizes.
8. **Platform layer**: discover saves from the table in section 6, show which
   are cloud-synced, and refuse to write to Xbox-signed saves (no public,
   verified re-signing procedure for KotOR).
9. **KotOR 2 support behind a flag** until each K2-specific field in section
   7 has been confirmed on a real K2 save.
