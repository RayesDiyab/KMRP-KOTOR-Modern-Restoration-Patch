//! One save folder, read whole into memory, changed there and written back together.
//!
//! Where things live (measured on real saves, see save-editor/docs/save-editor.md):
//! - the player: `Mod_PlayerList` of the last module's Module.ifo inside SAVEGAME.sav,
//!   and KotOR 2 also keeps `pc.utc` in SAVEGAME.sav; both are changed together;
//! - party members: `AVAILNPCn.utc` in SAVEGAME.sav, and a second copy in the current
//!   area's creature list when they stand there (the Ebon Hawk); both are changed;
//! - credits, party XP, influence, components: PARTYTABLE.res;
//! - the party's items: INVENTORY in SAVEGAME.sav;
//! - story switches and counters: GLOBALVARS.res.
//!
//! Only the files that changed are written, each to a new file first and then moved
//! over the old one, after a copy of the whole save folder has been made.

use crate::formats::erf::{Erf, RES_TYPE_GIT, RES_TYPE_IFO, RES_TYPE_RES, RES_TYPE_SAV, RES_TYPE_UTC};
use crate::formats::gff::{Gff, Struct, Value};
use crate::formats::tga;
use crate::games::Game;
use std::collections::BTreeSet;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

pub type Result<T> = std::result::Result<T, String>;

fn file_ci(dir: &Path, name: &str) -> Option<PathBuf> {
    fs::read_dir(dir)
        .ok()?
        .filter_map(|e| e.ok())
        .find(|e| e.file_name().to_string_lossy().eq_ignore_ascii_case(name))
        .map(|e| e.path())
}

fn read_gff(dir: &Path, name: &str) -> Result<(PathBuf, Gff)> {
    let path = file_ci(dir, name).ok_or_else(|| format!("{} is missing", name))?;
    let data = fs::read(&path).map_err(|e| format!("{}: {}", name, e))?;
    let gff = Gff::read(&data).map_err(|e| format!("{}: {}", name, e))?;
    Ok((path, gff))
}

/// What the save list shows, read from savenfo.res alone.
#[derive(Clone, Debug, Default)]
pub struct Summary {
    pub name: String,
    pub area: String,
    pub pc_name: String,
    pub seconds: i64,
    pub portraits: Vec<String>,
    pub modified: Option<std::time::SystemTime>,
    pub game: Option<Game>,
}

pub fn summary(folder: &Path) -> Option<Summary> {
    let (path, nfo) = read_gff(folder, "savenfo.res").ok()?;
    let r = &nfo.root;
    let mut name = r.string("SAVEGAMENAME").unwrap_or_default();
    if name.trim().is_empty() {
        // Quick and auto saves have no name of their own: "000001 - AUTOSAVE".
        let folder_name = folder.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
        name = folder_name.split_once(" - ").map(|(_, n)| n.to_string()).unwrap_or(folder_name);
        name = title_case(&name);
    }
    let portraits = (0..3).filter_map(|i| r.string(&format!("PORTRAIT{}", i))).filter(|p| !p.is_empty()).collect();
    Some(Summary {
        name,
        area: r.string("AREANAME").unwrap_or_default(),
        pc_name: r.string("PCNAME").unwrap_or_default(),
        seconds: r.int("TIMEPLAYED").unwrap_or(0),
        portraits,
        modified: fs::metadata(&path).and_then(|m| m.modified()).ok(),
        game: Some(game_of_nfo(r)),
    })
}

fn title_case(s: &str) -> String {
    if s.chars().any(|c| c.is_lowercase()) {
        return s.to_string();
    }
    s.split(' ')
        .map(|w| {
            let mut c = w.chars();
            c.next().map(|f| f.to_string() + &c.as_str().to_lowercase()).unwrap_or_default()
        })
        .collect::<Vec<_>>()
        .join(" ")
}

/// KotOR 2's savenfo carries fields KotOR 1's never has.
fn game_of_nfo(nfo: &Struct) -> Game {
    if nfo.get("PCNAME").is_some() || nfo.get("STORYHINT0").is_some() || nfo.get("TIMESTAMP").is_some() {
        Game::K2
    } else {
        Game::K1
    }
}

pub fn peek_game(folder: &Path) -> Option<Game> {
    summary(folder).and_then(|s| s.game)
}

pub fn screenshot(folder: &Path) -> Option<tga::Image> {
    tga::decode(&fs::read(file_ci(folder, "Screen.tga")?).ok()?)
}

/// A creature in the save the editor can change.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Who {
    Player,
    Npc(usize),
}

pub struct Save {
    pub game: Game,
    pub folder: PathBuf,
    pub nfo: Gff,
    pub party: Gff,
    pub globals: Option<Gff>,
    nfo_path: PathBuf,
    party_path: PathBuf,
    globals_path: Option<PathBuf>,
    archive_path: PathBuf,
    archive: Erf,
    /// The last module's nested save, with its Module.ifo and area .git read.
    module_name: String,
    module: Option<Erf>,
    ifo: Option<Gff>,
    git: Option<(String, Gff)>,
    /// GFF resources of SAVEGAME.sav that were read: AVAILNPCn, pc, INVENTORY.
    loaded: Vec<(String, u16, Gff)>,
    dirty: BTreeSet<&'static str>,
    dirty_archive: BTreeSet<(String, u16)>,
    /// SAVEGAME.sav changed in memory (a module flushed into it).
    archive_dirty: bool,
    /// What changed, by a key per value, so changing one value twice counts once.
    pub changes: BTreeSet<String>,
}

impl Save {
    pub fn open(folder: &Path) -> Result<Save> {
        let (nfo_path, nfo) = read_gff(folder, "savenfo.res")?;
        let (party_path, party) = read_gff(folder, "PARTYTABLE.res")?;
        let globals = read_gff(folder, "GLOBALVARS.res").ok();
        let archive_path = file_ci(folder, "SAVEGAME.sav").ok_or("SAVEGAME.sav is missing")?;
        let archive = Erf::read(&fs::read(&archive_path).map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
        let game = game_of_nfo(&nfo.root);
        let module_name = nfo.root.string("LASTMODULE").unwrap_or_default();
        let mut save = Save {
            game,
            folder: folder.to_path_buf(),
            nfo,
            party,
            globals_path: globals.as_ref().map(|g| g.0.clone()),
            globals: globals.map(|g| g.1),
            nfo_path,
            party_path,
            archive_path,
            archive,
            module_name,
            module: None,
            ifo: None,
            git: None,
            loaded: Vec::new(),
            dirty: BTreeSet::new(),
            dirty_archive: BTreeSet::new(),
            archive_dirty: false,
            changes: BTreeSet::new(),
        };
        save.load_module();
        for r in save.archive.resources.iter() {
            let lower = r.name.to_ascii_lowercase();
            let wanted = (r.kind == RES_TYPE_UTC && (lower.starts_with("availnpc") || lower == "pc"))
                || (r.kind == RES_TYPE_RES && lower == "inventory");
            if wanted {
                if let Ok(g) = Gff::read(&r.data) {
                    save.loaded.push((r.name.clone(), r.kind, g));
                }
            }
        }
        if save.player().is_none() {
            return Err("this save has no player character in it".into());
        }
        Ok(save)
    }

    fn load_module(&mut self) {
        let Some(r) = self.archive.find(&self.module_name, RES_TYPE_SAV) else { return };
        let Ok(module) = Erf::read(&r.data) else { return };
        self.ifo = module
            .resources
            .iter()
            .find(|r| r.kind == RES_TYPE_IFO)
            .and_then(|r| Gff::read(&r.data).ok());
        self.git = module
            .resources
            .iter()
            .find(|r| r.kind == RES_TYPE_GIT)
            .and_then(|r| Gff::read(&r.data).ok().map(|g| (r.name.clone(), g)));
        self.module = Some(module);
    }

    /// Puts the current module's changed .ifo and .git back into SAVEGAME.sav (in memory).
    fn flush_module(&mut self) {
        if !(self.dirty.contains("ifo") || self.dirty.contains("git")) {
            return;
        }
        if let Some(module) = self.module.as_mut() {
            if let (true, Some(ifo)) = (self.dirty.contains("ifo"), self.ifo.as_ref()) {
                if let Some(r) = module.resources.iter_mut().find(|r| r.kind == RES_TYPE_IFO) {
                    r.data = ifo.write();
                }
            }
            if let (true, Some((name, git))) = (self.dirty.contains("git"), self.git.as_ref()) {
                if let Some(r) = module.find_mut(name, RES_TYPE_GIT) {
                    r.data = git.write();
                }
            }
            let bytes = module.write();
            if let Some(r) = self.archive.find_mut(&self.module_name, RES_TYPE_SAV) {
                r.data = bytes;
            }
        }
        self.dirty.remove("ifo");
        self.dirty.remove("git");
        self.archive_dirty = true;
    }

    /// The area objects (.git) of another module the save has been to, as it left them.
    pub fn module_git(&self, module: &str) -> Option<Gff> {
        if module.eq_ignore_ascii_case(&self.module_name) {
            return self.git.as_ref().map(|(_, g)| g.clone());
        }
        let r = self.archive.resources.iter().find(|r| r.kind == RES_TYPE_SAV && r.name.eq_ignore_ascii_case(module))?;
        let erf = Erf::read(&r.data).ok()?;
        let g = erf.resources.iter().find(|r| r.kind == RES_TYPE_GIT)?;
        Gff::read(&g.data).ok()
    }

    /// The module the save resumes in.
    pub fn module_name(&self) -> &str {
        &self.module_name
    }

    /// The modules this save has been to: the module saves in SAVEGAME.sav.
    pub fn visited_modules(&self) -> Vec<String> {
        self.archive.resources.iter().filter(|r| r.kind == RES_TYPE_SAV).map(|r| r.name.to_ascii_lowercase()).collect()
    }

    /// Moves the player (every copy) to `pos` in the current area, facing `facing`.
    pub fn move_player(&mut self, pos: [f32; 3], facing: Option<f32>) {
        self.edit(Who::Player, "position", |c| {
            crate::area::set_position(c, pos);
            if let Some(a) = facing {
                c.set_float("XOrientation", a.cos());
                c.set_float("YOrientation", a.sin());
            }
        });
    }

    /// Moves the player to `pos` in another module this save has been to: the player goes
    /// into that module's player list, and the save resumes there (savenfo LASTMODULE and
    /// AREANAME). The game reads the player from the module it resumes in.
    pub fn move_to_module(&mut self, module: &str, pos: [f32; 3], area_name: &str) -> Result<()> {
        if module.eq_ignore_ascii_case(&self.module_name) {
            self.move_player(pos, None);
            return Ok(());
        }
        let player = self.player().cloned().ok_or("this save has no player")?;
        let target = self
            .archive
            .resources
            .iter()
            .find(|r| r.kind == RES_TYPE_SAV && r.name.eq_ignore_ascii_case(module))
            .map(|r| r.name.clone())
            .ok_or("this save has not been to that area")?;
        self.flush_module();
        // The target module, with the player put in.
        let data = self.archive.find(&target, RES_TYPE_SAV).unwrap().data.clone();
        let mut erf = Erf::read(&data).map_err(|e| e.to_string())?;
        let ifo_res = erf.resources.iter_mut().find(|r| r.kind == RES_TYPE_IFO).ok_or("that area's save has no module file")?;
        let mut ifo = Gff::read(&ifo_res.data).map_err(|e| e.to_string())?;
        let mut moved = player;
        crate::area::set_position(&mut moved, pos);
        let old_self = ifo.root.list("Mod_PlayerList").and_then(|l| l.first()).cloned();
        if let Some(o) = old_self.as_ref() {
            moved.id = o.id;
        }
        // Object ids are each module's own: the player takes the id that module gave it,
        // and every item it carries a new one from the module's counter, so nothing clashes
        // with that area's objects; effects naming an old id are pointed at the new one.
        let mut ids: Vec<(u32, u32)> = Vec::new();
        if let (Some(old), Some(new)) = (moved.int("ObjectId"), old_self.as_ref().and_then(|o| o.int("ObjectId"))) {
            ids.push((old as u32, new as u32));
            moved.set("ObjectId", Value::Dword(new as u32));
        }
        if let Some(area) = old_self.as_ref().and_then(|o| o.int("AreaId")) {
            moved.set_int("AreaId", area, Value::Dword(0));
        }
        let mut next = ifo.root.int("Mod_NextObjId0").unwrap_or(0x10000) as u32;
        for list in ["Equip_ItemList", "ItemList"] {
            if let Some(items) = moved.list_mut(list) {
                for it in items.iter_mut() {
                    if let Some(old) = it.int("ObjectId") {
                        ids.push((old as u32, next));
                        it.set("ObjectId", Value::Dword(next));
                        next += 1;
                    }
                }
            }
        }
        ifo.root.set_int("Mod_NextObjId0", next as i64, Value::Dword(0));
        if let Some(effects) = moved.list_mut("EffectList") {
            for e in effects.iter_mut() {
                if let Some(c) = e.int("CreatorId") {
                    if let Some((_, n)) = ids.iter().find(|(o, _)| *o == c as u32) {
                        e.set("CreatorId", Value::Dword(*n));
                    }
                }
            }
        }
        ifo.root.set("Mod_PlayerList", Value::List(vec![moved]));
        ifo_res.data = ifo.write();
        let bytes = erf.write();
        self.archive.find_mut(&target, RES_TYPE_SAV).unwrap().data = bytes;
        self.archive_dirty = true;
        let name_bytes = crate::text::encode(area_name);
        let module_bytes = target.as_bytes().to_vec();
        self.edit_nfo(|n| {
            n.set("LASTMODULE", Value::String(module_bytes));
            n.set("AREANAME", Value::String(name_bytes));
        });
        self.module_name = target;
        self.load_module();
        self.changed("player.module");
        Ok(())
    }

    pub fn changed(&mut self, key: impl Into<String>) {
        self.changes.insert(key.into());
    }

    fn loaded(&self, name: &str, kind: u16) -> Option<&Gff> {
        self.loaded.iter().find(|(n, k, _)| *k == kind && n.eq_ignore_ascii_case(name)).map(|(_, _, g)| g)
    }

    fn loaded_mut(&mut self, name: &str, kind: u16) -> Option<&mut Gff> {
        let found = self.loaded.iter_mut().find(|(n, k, _)| *k == kind && n.eq_ignore_ascii_case(name))?;
        self.dirty_archive.insert((found.0.clone(), kind));
        Some(&mut found.2)
    }

    // ---- creatures ----

    pub fn player(&self) -> Option<&Struct> {
        if let Some(p) = self.ifo.as_ref().and_then(|i| i.root.list("Mod_PlayerList")).and_then(|l| l.first()) {
            return Some(p);
        }
        self.loaded("pc", RES_TYPE_UTC).map(|g| &g.root)
    }

    pub fn creature(&self, who: Who) -> Option<&Struct> {
        match who {
            Who::Player => self.player(),
            Who::Npc(i) => self.loaded(&format!("availnpc{}", i), RES_TYPE_UTC).map(|g| &g.root),
        }
    }

    /// Applies `f` to every copy of the creature the save holds.
    pub fn edit(&mut self, who: Who, key: &str, f: impl Fn(&mut Struct)) {
        match who {
            Who::Player => {
                if let Some(p) = self.ifo.as_mut().and_then(|i| i.root.list_mut("Mod_PlayerList")).and_then(|l| l.first_mut()) {
                    f(p);
                    self.dirty.insert("ifo");
                }
                if let Some(pc) = self.loaded_mut("pc", RES_TYPE_UTC) {
                    f(&mut pc.root);
                }
            }
            Who::Npc(i) => {
                let tag = self.creature(who).and_then(|c| c.string("Tag")).unwrap_or_default();
                if let Some(npc) = self.loaded_mut(&format!("availnpc{}", i), RES_TYPE_UTC) {
                    f(&mut npc.root);
                }
                if !tag.is_empty() {
                    if let Some((_, git)) = self.git.as_mut() {
                        let mut touched = false;
                        if let Some(list) = git.root.list_mut("Creature List") {
                            for c in list.iter_mut().filter(|c| c.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(&tag))) {
                                f(c);
                                touched = true;
                            }
                        }
                        if touched {
                            self.dirty.insert("git");
                        }
                    }
                }
            }
        }
        self.changed(format!("{:?}.{}", who, key));
    }

    /// The party members whose creature is in the save, by NPC index.
    pub fn npcs(&self) -> Vec<usize> {
        let mut out: Vec<usize> = self
            .loaded
            .iter()
            .filter_map(|(n, k, _)| {
                if *k != RES_TYPE_UTC {
                    return None;
                }
                n.to_ascii_lowercase().strip_prefix("availnpc")?.parse().ok()
            })
            .collect();
        out.sort();
        out
    }

    /// Brings party member `npc` over from another save of the same game: their
    /// creature replaces (or becomes) AVAILNPCn here, and they are listed as recruited.
    pub fn import_npc(&mut self, other: &Save, npc: usize) -> Result<()> {
        if other.game != self.game {
            return Err("that save is from the other game".into());
        }
        let creature = other
            .loaded(&format!("availnpc{}", npc), RES_TYPE_UTC)
            .ok_or("that save does not have this party member")?
            .clone();
        let name = format!("availnpc{}", npc);
        let display = self
            .archive
            .resources
            .iter()
            .find(|r| r.name.to_ascii_lowercase().starts_with("availnpc"))
            .map(|r| if r.name.chars().any(|c| c.is_uppercase()) { name.to_uppercase() } else { name.clone() })
            .unwrap_or_else(|| name.clone());
        if let Some(slot) = self.loaded.iter_mut().find(|(n, k, _)| *k == RES_TYPE_UTC && n.eq_ignore_ascii_case(&name)) {
            slot.2 = creature;
        } else {
            // Keep the archive's order: the members come first, by index.
            let at = self
                .archive
                .resources
                .iter()
                .position(|r| {
                    r.kind != RES_TYPE_UTC
                        || r.name.to_ascii_lowercase().strip_prefix("availnpc").and_then(|n| n.parse::<usize>().ok()).map_or(true, |n| n > npc)
                })
                .unwrap_or(self.archive.resources.len());
            self.archive.resources.insert(
                at,
                crate::formats::erf::Resource { name: display.clone(), kind: RES_TYPE_UTC, id: 0, data: Vec::new() },
            );
            self.loaded.push((display, RES_TYPE_UTC, creature));
        }
        self.dirty_archive.insert((name, RES_TYPE_UTC));
        self.set_recruited(npc, true);
        self.set_selectable(npc, true);
        self.changed(format!("npc{}.import", npc));
        Ok(())
    }

    // ---- the party table ----

    pub fn party_int(&self, label: &str) -> Option<i64> {
        self.party.root.int(label)
    }

    pub fn set_party_int(&mut self, label: &str, value: i64) {
        if self.party.root.set_int(label, value, Value::Dword(0)) {
            self.dirty.insert("party");
            self.changed(format!("party.{}", label));
        }
    }

    fn npc_list_int(&self, list: &str, index: usize, field: &str) -> Option<i64> {
        self.party.root.list(list)?.get(index)?.int(field)
    }

    fn set_npc_list_int(&mut self, list: &str, index: usize, field: &str, value: i64) {
        if let Some(entry) = self.party.root.list_mut(list).and_then(|l| l.get_mut(index)) {
            entry.set_int(field, value, Value::Byte(0));
            self.dirty.insert("party");
            self.changed(format!("party.{}.{}.{}", list, index, field));
        }
    }

    /// Influence (KotOR 2): 0 to 100, or -1 for someone not met yet.
    pub fn influence(&self, npc: usize) -> Option<i64> {
        self.npc_list_int("PT_INFLUENCE", npc, "PT_NPC_INFLUENCE")
    }

    pub fn set_influence(&mut self, npc: usize, value: i64) {
        self.set_npc_list_int("PT_INFLUENCE", npc, "PT_NPC_INFLUENCE", value.clamp(0, 100));
    }

    pub fn npc_count(&self) -> usize {
        self.party.root.list("PT_AVAIL_NPCS").map_or(0, |l| l.len())
    }

    /// Recruited: the party screen lists them.
    pub fn recruited(&self, npc: usize) -> bool {
        self.npc_list_int("PT_AVAIL_NPCS", npc, "PT_NPC_AVAIL") == Some(1)
    }

    /// Only a member whose creature the save holds can be listed; the game loads it
    /// from AVAILNPCn when they join.
    pub fn set_recruited(&mut self, npc: usize, on: bool) -> bool {
        if on && !self.npcs().contains(&npc) {
            return false;
        }
        self.set_npc_list_int("PT_AVAIL_NPCS", npc, "PT_NPC_AVAIL", on as i64);
        if !on {
            self.set_npc_list_int("PT_AVAIL_NPCS", npc, "PT_NPC_SELECT", 1);
        }
        true
    }

    /// Selectable: not locked out of the party screen by the story.
    pub fn selectable(&self, npc: usize) -> bool {
        self.npc_list_int("PT_AVAIL_NPCS", npc, "PT_NPC_SELECT") != Some(0)
    }

    pub fn set_selectable(&mut self, npc: usize, on: bool) {
        self.set_npc_list_int("PT_AVAIL_NPCS", npc, "PT_NPC_SELECT", on as i64);
    }

    pub fn in_party(&self, npc: usize) -> bool {
        self.party
            .root
            .list("PT_MEMBERS")
            .map_or(false, |l| l.iter().any(|m| m.int("PT_MEMBER_ID") == Some(npc as i64)))
    }

    // ---- inventory ----

    pub fn inventory(&self) -> Vec<Struct> {
        self.loaded("inventory", RES_TYPE_RES)
            .and_then(|g| g.root.list("ItemList"))
            .cloned()
            .unwrap_or_default()
    }

    pub fn edit_inventory(&mut self, key: &str, f: impl FnOnce(&mut Vec<Struct>)) {
        if let Some(inv) = self.loaded_mut("inventory", RES_TYPE_RES) {
            if inv.root.list("ItemList").is_none() {
                inv.root.set("ItemList", Value::List(Vec::new()));
            }
            f(inv.root.list_mut("ItemList").unwrap());
            self.changed(format!("inventory.{}", key));
        }
    }

    // ---- equipment ----

    /// A new object id from the module's counter (Mod_NextObjId0), which then moves on;
    /// the area's highest id + 1 when the module has no counter.
    fn new_object_id(&mut self) -> u32 {
        if let Some(ifo) = self.ifo.as_mut() {
            if let Some(next) = ifo.root.int("Mod_NextObjId0") {
                ifo.root.set_int("Mod_NextObjId0", next + 1, Value::Dword(0));
                self.dirty.insert("ifo");
                return next as u32;
            }
        }
        self.git.as_ref().map(|(_, g)| crate::area::next_object_id(&g.root)).unwrap_or(0x10000)
    }

    /// Equips one of inventory item `index` in `slot`, on every copy of the creature; what
    /// was in the slot goes back to the party inventory.
    pub fn equip(&mut self, who: Who, slot: u32, index: usize) -> bool {
        let inventory = self.inventory();
        let Some(mut item) = inventory.get(index).cloned() else { return false };
        let stack = item.int("StackSize").unwrap_or(1);
        item.set_int("StackSize", 1, Value::Word(1));
        let old = self.creature(who).and_then(|c| crate::creature::in_slot(c, slot)).cloned();
        let id = self.new_object_id();
        self.edit(who, &format!("equip{}", slot), |c| {
            crate::creature::unequip(c, slot);
            crate::creature::equip(c, slot, item.clone(), id);
        });
        self.edit_inventory(&format!("equip{}", slot), |items| {
            if stack > 1 {
                items[index].set_int("StackSize", stack - 1, Value::Word(1));
            } else {
                items.remove(index);
            }
            if let Some(mut o) = old {
                o.id = 0;
                o.fields.retain(|(l, _)| l != "ObjectId");
                items.push(o);
            }
        });
        true
    }

    /// Takes the item out of `slot` on every copy and puts it in the party inventory.
    pub fn unequip(&mut self, who: Who, slot: u32) -> bool {
        let Some(mut item) = self.creature(who).and_then(|c| crate::creature::in_slot(c, slot)).cloned() else { return false };
        self.edit(who, &format!("equip{}", slot), |c| {
            crate::creature::unequip(c, slot);
        });
        item.id = 0;
        item.fields.retain(|(l, _)| l != "ObjectId");
        self.edit_inventory(&format!("unequip{}", slot), |items| items.push(item));
        true
    }

    /// The party inventory replaced by another save's of the same game.
    pub fn copy_inventory(&mut self, other: &Save) -> Result<()> {
        if other.game != self.game {
            return Err("that save is from the other game".into());
        }
        let items = other.inventory();
        self.edit_inventory("copied", |list| *list = items);
        Ok(())
    }

    // ---- the active party ----

    pub fn party_members(&self) -> Vec<usize> {
        self.party
            .root
            .list("PT_MEMBERS")
            .map(|l| l.iter().filter_map(|m| m.int("PT_MEMBER_ID")).map(|i| i as usize).collect())
            .unwrap_or_default()
    }

    /// Who travels with the player: two at most, each recruited and held in the save. The
    /// area is left alone: on the Ebon Hawk the game stands every member around the ship
    /// itself (a member taken out of the Hawk's area went missing in a test, 2026-10-22).
    pub fn set_party_members(&mut self, members: &[usize]) -> Result<()> {
        if members.len() > 2 {
            return Err("two party members at most".into());
        }
        for &m in members {
            if self.creature(Who::Npc(m)).is_none() {
                return Err("that member is not in this save".into());
            }
        }
        let shape = self.party.root.list("PT_MEMBERS").and_then(|l| l.first().cloned()).unwrap_or_else(|| {
            let mut s = Struct::new(0);
            s.set("PT_MEMBER_ID", Value::Int(0));
            s.set("PT_IS_LEADER", Value::Byte(0));
            s
        });
        let before = self.party_members();
        let list: Vec<Struct> = members
            .iter()
            .map(|&m| {
                let mut e = shape.clone();
                e.set_int("PT_MEMBER_ID", m as i64, Value::Int(0));
                e.set_int("PT_IS_LEADER", 0, Value::Byte(0));
                e
            })
            .collect();
        let controlled = self.party.root.int("PT_CONTROLLED_NP").unwrap_or(-1);
        self.edit_party_table("members", |p| {
            p.set("PT_MEMBERS", Value::List(list));
            p.set_int("PT_NUM_MEMBERS", members.len() as i64, Value::Byte(0));
            if controlled >= 0 && !members.contains(&(controlled as usize)) {
                p.set_int("PT_CONTROLLED_NP", -1, Value::Int(0));
            }
        });
        for &m in members.iter().filter(|m| !before.contains(m)) {
            self.set_recruited(m, true);
        }
        Ok(())
    }

    // ---- quests ----

    /// The journal entries as (quest tag, stage).
    pub fn quests(&self) -> Vec<(String, i64)> {
        self.party
            .root
            .list("JNL_Entries")
            .map(|l| l.iter().map(|e| (e.string("JNL_PlotID").unwrap_or_default(), e.int("JNL_State").unwrap_or(0))).collect())
            .unwrap_or_default()
    }

    /// Puts quest `tag` at `stage`, adding it to the journal when it is not there yet;
    /// a new entry takes the date and time of the newest entry already written.
    pub fn set_quest(&mut self, tag: &str, stage: i64) {
        let tag = tag.to_string();
        self.edit_party_table(&format!("quest.{}", tag), |p| {
            if p.list("JNL_Entries").is_none() {
                p.set("JNL_Entries", Value::List(Vec::new()));
            }
            let list = p.list_mut("JNL_Entries").unwrap();
            if let Some(e) = list.iter_mut().find(|e| e.string("JNL_PlotID").map_or(false, |t| t.eq_ignore_ascii_case(&tag))) {
                e.set_int("JNL_State", stage, Value::Int(0));
                return;
            }
            let mut e = list.last().cloned().unwrap_or_else(|| {
                let mut s = Struct::new(0);
                s.set("JNL_PlotID", Value::String(Vec::new()));
                s.set("JNL_State", Value::Int(0));
                s.set("JNL_Date", Value::Dword(0));
                s.set("JNL_Time", Value::Dword(0));
                s
            });
            e.set("JNL_PlotID", Value::String(crate::text::encode(&tag)));
            e.set_int("JNL_State", stage, Value::Int(0));
            list.push(e);
        });
    }

    pub fn remove_quest(&mut self, tag: &str) {
        let tag = tag.to_string();
        self.edit_party_table(&format!("quest.{}", tag), |p| {
            if let Some(list) = p.list_mut("JNL_Entries") {
                list.retain(|e| !e.string("JNL_PlotID").map_or(false, |t| t.eq_ignore_ascii_case(&tag)));
            }
        });
    }

    // ---- globals ----

    pub fn edit_globals(&mut self, key: &str, f: impl FnOnce(&mut Struct)) {
        if let Some(g) = self.globals.as_mut() {
            f(&mut g.root);
            self.dirty.insert("globals");
            self.changed(format!("globals.{}", key));
        }
    }

    pub fn area_git(&self) -> Option<&Gff> {
        self.git.as_ref().map(|(_, g)| g)
    }

    pub fn edit_area(&mut self, key: &str, f: impl FnOnce(&mut Struct)) {
        if let Some((_, g)) = self.git.as_mut() {
            f(&mut g.root);
            self.dirty.insert("git");
            self.changed(format!("area.{}", key));
        }
    }

    /// Adds a creature to the current area with ids nothing else uses: its own from the
    /// module's counter, and one for every full item it carries. Returns its id.
    pub fn spawn_creature(&mut self, mut c: Struct) -> u32 {
        let id = self.new_object_id();
        c.set("ObjectId", Value::Dword(id));
        let items = crate::area::creature_items_mut(&mut c).len();
        let ids: Vec<u32> = (0..items).map(|_| self.new_object_id()).collect();
        for (item, new) in crate::area::creature_items_mut(&mut c).into_iter().zip(ids) {
            item.set("ObjectId", Value::Dword(new));
        }
        self.edit_area(&format!("spawn{}", id), move |git| crate::area::add_creature(git, c));
        id
    }

    /// Sends the player to `module` the way a door between areas does: an area-transition
    /// event (EVENT_AREA_TRANSITION, 26) queued in the current module, which the game runs
    /// right after the save loads. The game then makes the trip itself: it stores this area,
    /// loads the target fresh from its own files when the save has not been there (as on a
    /// first arrival, with the area's arrival scripts), and puts the player and the party at
    /// `waypoint`. The event's layout is the game's (struct 0xABCD holding a script event,
    /// 0xEEEE, whose eight strings are the module, the waypoint and six movies); from the
    /// maintainer's own reverse engineering of KotOR 1 (area event handler 0x0050D6C0).
    /// `movies` (up to six) play before the area loads, as a script's StartNewModule plays
    /// them (the escape pod's 01c before the vision, for one).
    pub fn queue_transition(&mut self, module: &str, waypoint: &str, movies: &[&str]) -> Result<()> {
        let ifo = self.ifo.as_mut().ok_or("this save has no module file")?;
        let day = ifo.root.int("Mod_PauseDay").unwrap_or(0);
        let time = ifo.root.int("Mod_PauseTime").unwrap_or(0);
        let area = ifo.root.list("Mod_Area_list").and_then(|l| l.first()).and_then(|a| a.int("ObjectId")).unwrap_or(1);
        let text = |t: &str| {
            let mut p = Struct::new(0x69);
            p.set("Parameter", Value::String(t.as_bytes().to_vec()));
            p
        };
        let mut data = Struct::new(0xEEEE);
        data.set("EventType", Value::Word(0));
        data.set("IntList", Value::List(Vec::new()));
        data.set("FloatList", Value::List(Vec::new()));
        let mut strings = vec![text(module), text(waypoint)];
        strings.extend((0..6).map(|i| text(movies.get(i).copied().unwrap_or(""))));
        data.set("StringList", Value::List(strings));
        data.set("ObjectList", Value::List(Vec::new()));
        let mut event = Struct::new(0xABCD);
        event.set("Day", Value::Dword(day as u32));
        // Due at the moment the save was made, so it runs as soon as the game does (a second
        // later waited, on the Endar Spire, until the player first did something).
        event.set("Time", Value::Dword(time as u32));
        event.set("ObjectId", Value::Dword(area as u32));
        event.set("CallerId", Value::Dword(area as u32));
        event.set("EventId", Value::Dword(26));
        event.set("EventData", Value::Struct(data));
        if ifo.root.list("EventQueue").is_none() {
            ifo.root.set("EventQueue", Value::List(Vec::new()));
        }
        // First in the queue: the game looks at its queue in order, and behind the save's own
        // delayed events (Trask's opening, on the Endar Spire) the trip waited until those
        // ran or the player did something (the maintainer's test, 2026-10-23).
        ifo.root.list_mut("EventQueue").unwrap().insert(0, event);
        self.dirty.insert("ifo");
        self.changed(format!("travel.{}", module.to_ascii_lowercase()));
        Ok(())
    }

    /// Changes the saved objects (.git) of `module`: the current area, or another area this
    /// save has been to. Returns false when the save has not been there (the game then
    /// builds that area fresh from its own files when the player arrives).
    pub fn edit_module_git(&mut self, module: &str, key: &str, f: impl FnOnce(&mut Struct)) -> bool {
        if module.eq_ignore_ascii_case(&self.module_name) {
            if self.git.is_none() {
                return false;
            }
            self.edit_area(key, f);
            return true;
        }
        let Some(name) = self
            .archive
            .resources
            .iter()
            .find(|r| r.kind == RES_TYPE_SAV && r.name.eq_ignore_ascii_case(module))
            .map(|r| r.name.clone())
        else {
            return false;
        };
        let data = self.archive.find(&name, RES_TYPE_SAV).unwrap().data.clone();
        let Ok(mut erf) = Erf::read(&data) else { return false };
        let Some(res) = erf.resources.iter_mut().find(|r| r.kind == RES_TYPE_GIT) else { return false };
        let Ok(mut git) = Gff::read(&res.data) else { return false };
        f(&mut git.root);
        res.data = git.write();
        let bytes = erf.write();
        self.archive.find_mut(&name, RES_TYPE_SAV).unwrap().data = bytes;
        self.archive_dirty = true;
        self.changed(format!("{}.{}", module.to_ascii_lowercase(), key));
        true
    }

    pub fn edit_nfo(&mut self, f: impl FnOnce(&mut Struct)) {
        f(&mut self.nfo.root);
        self.dirty.insert("nfo");
    }

    /// The name the game's Load screen shows.
    pub fn rename(&mut self, name: &str) {
        let bytes = crate::text::encode(name);
        self.edit_nfo(|n| n.set("SAVEGAMENAME", Value::String(bytes)));
        self.changed("nfo.name");
    }

    pub fn edit_party_table(&mut self, key: &str, f: impl FnOnce(&mut Struct)) {
        f(&mut self.party.root);
        self.dirty.insert("party");
        self.changed(format!("party.{}", key));
    }

    // ---- writing ----

    /// Copies the whole save folder into `backups`, then writes every changed file.
    /// Returns the backup folder.
    pub fn write(&mut self, backups: &Path) -> Result<PathBuf> {
        let backup = backup_folder(backups, self.game, &self.folder);
        copy_dir(&self.folder, &backup).map_err(|e| format!("the backup could not be made: {}", e))?;

        self.flush_module();
        let module_dirty = self.archive_dirty;
        for (name, kind) in self.dirty_archive.clone() {
            if let Some(g) = self.loaded(&name, kind) {
                let bytes = g.write();
                if let Some(r) = self.archive.find_mut(&name, kind) {
                    r.data = bytes;
                }
            }
        }
        let mut files: Vec<(PathBuf, Vec<u8>)> = Vec::new();
        if module_dirty || !self.dirty_archive.is_empty() {
            files.push((self.archive_path.clone(), self.archive.write()));
        }
        // Keep the load screen's copies in step with the party table.
        if self.dirty.contains("party") {
            let seconds = self.party.root.int("PT_PLAYEDSECONDS");
            let cheat = self.party.root.int("PT_CHEAT_USED");
            let name = self.party.root.string("PT_PCNAME");
            let nfo = &mut self.nfo.root;
            if let Some(s) = seconds {
                nfo.set_int("TIMEPLAYED", s, Value::Dword(0));
            }
            if let Some(c) = cheat {
                nfo.set_int("CHEATUSED", c, Value::Byte(0));
            }
            if let (Some(n), true) = (name, nfo.get("PCNAME").is_some()) {
                nfo.set("PCNAME", Value::String(crate::text::encode(&n)));
            }
            self.dirty.insert("nfo");
        }
        if self.dirty.contains("party") {
            files.push((self.party_path.clone(), self.party.write()));
        }
        if self.dirty.contains("nfo") {
            files.push((self.nfo_path.clone(), self.nfo.write()));
        }
        if let (true, Some(g), Some(p)) = (self.dirty.contains("globals"), self.globals.as_ref(), self.globals_path.as_ref()) {
            files.push((p.clone(), g.write()));
        }
        // Every new file is written in full before any old one is replaced.
        let mut staged = Vec::new();
        for (path, bytes) in &files {
            let tmp = path.with_extension("kmrp-new");
            fs::write(&tmp, bytes).map_err(|e| format!("{}: {}", path.display(), e))?;
            staged.push((tmp, path.clone()));
        }
        for (tmp, path) in staged {
            fs::rename(&tmp, &path).map_err(|e| format!("{}: {}", path.display(), e))?;
        }
        self.dirty.clear();
        self.dirty_archive.clear();
        self.archive_dirty = false;
        self.changes.clear();
        Ok(backup)
    }
}

fn backup_folder(backups: &Path, _game: Game, folder: &Path) -> PathBuf {
    let name = folder.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_else(|| "save".into());
    let stamp = timestamp();
    let mut path = backups.join(&name).join(&stamp);
    let mut n = 2;
    while path.exists() {
        path = backups.join(&name).join(format!("{} ({})", stamp, n));
        n += 1;
    }
    path
}

/// Where a save's backups go: "Save Editor Backup" in the folder that holds the save (the
/// game's saves folder), as the maintainer asked on 2026-10-22. A Steam Cloud save of
/// KotOR 2 keeps its backups in the game's local saves folder instead, so Steam does not
/// upload them.
pub fn backup_root(folder: &Path, game_root: Option<&Path>) -> PathBuf {
    let parent = folder.parent().unwrap_or(folder);
    let cloud = folder.ancestors().any(|a| a.file_name().map_or(false, |n| n.eq_ignore_ascii_case("cloudsaves")));
    match (cloud, game_root) {
        (true, Some(root)) => root.join("saves").join("Save Editor Backup"),
        _ => parent.join("Save Editor Backup"),
    }
}

/// "2026-10-22 14-05-09", in UTC (no time zone database needed).
pub fn timestamp() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    let (y, m, d) = civil(secs.div_euclid(86_400));
    let t = secs.rem_euclid(86_400);
    format!("{:04}-{:02}-{:02} {:02}-{:02}-{:02}", y, m, d, t / 3600, t % 3600 / 60, t % 60)
}

/// Days since 1970-01-01 to a calendar date (Howard Hinnant's algorithm).
pub fn civil(days: i64) -> (i64, i64, i64) {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    (yoe + era * 400 + (m <= 2) as i64, m, d)
}

fn copy_dir(from: &Path, to: &Path) -> io::Result<()> {
    fs::create_dir_all(to)?;
    for e in fs::read_dir(from)? {
        let e = e?;
        let target = to.join(e.file_name());
        if e.path().is_dir() {
            copy_dir(&e.path(), &target)?;
        } else {
            fs::copy(e.path(), target)?;
        }
    }
    Ok(())
}
