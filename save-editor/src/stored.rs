//! A played-through stored copy of an area the save never visited: what the game itself
//! keeps in SAVEGAME.sav (a nested module save, type 2057: module.ifo, the .are, the .git)
//! for an area the player has left, here built from the game's own files in the state a
//! full run leaves it. Travelling there later (the Ebon Hawk, a door, or the editor's
//! area-transition event) loads it as a return visit: the stored copy wins over the shipped
//! module, the area's scripts run as on any return, and what the copy holds is what the
//! player sees (the maintainer's own reverse engineering of KotOR 1: LoadModule 0x004B95B0,
//! the IFO loader 0x004C9050, the GIT loader 0x0050DD80; stored-area research, 2026-10-23).
//!
//! Every object is a full struct (the template's fields plus the game .git entry's instance
//! fields and an ObjectId), because a .git built from templates (UseTemplates) takes each
//! door's lock and each container's contents from the template and cannot carry a played
//! state. The struct ids are the ones the list loaders check.

use crate::formats::gff::{Gff, Struct, Value};
use crate::gamedata::GameData;
use crate::map::ModuleFiles;

/// What "played through" means for one area, from the chapter's milestone (IDs only).
#[derive(Default, Debug, Clone)]
pub struct Cleared {
    /// Creatures and placeables gone for good (killed, picked up, left), by tag.
    pub remove: Vec<String>,
    /// Doors that end open, and that end unlocked, by tag.
    pub open: Vec<String>,
    pub unlock: Vec<String>,
    /// Containers whose loot the player already has, by tag.
    pub looted: Vec<String>,
    /// The area's local bits (the .git root's SWVarTable), the module's (module.ifo), and
    /// triggers' fired bits by tag.
    pub area_bits: Vec<u32>,
    pub module_bits: Vec<u32>,
    pub trigger_bits: Vec<(String, u32)>,
    /// Local bits and numbers on other objects (doors, placeables, creatures), by tag, and
    /// local numbers of the area and the module (SetLocalNumber index: the ByteArray).
    pub object_bits: Vec<(String, u32)>,
    pub object_numbers: Vec<(String, u32, i64)>,
    pub area_numbers: Vec<(u32, i64)>,
    pub module_numbers: Vec<(u32, i64)>,
    /// Encounters a full run used up, by tag.
    pub exhausted: Vec<String>,
}

/// The local bits and numbers the run leaves on the object with this struct's tag.
fn locals_of(s: &Struct, cleared: &Cleared) -> (Vec<u32>, Vec<(u32, i64)>) {
    let tag = s.string("Tag").unwrap_or_default();
    let bits = cleared
        .object_bits
        .iter()
        .chain(cleared.trigger_bits.iter())
        .filter(|(t, _)| t.eq_ignore_ascii_case(&tag))
        .map(|(_, b)| *b)
        .collect();
    let numbers = cleared.object_numbers.iter().filter(|(t, _, _)| t.eq_ignore_ascii_case(&tag)).map(|(_, i, n)| (*i, *n)).collect();
    (bits, numbers)
}

fn tag_in(s: &Struct, list: &[String]) -> bool {
    s.string("Tag").map_or(false, |t| list.iter().any(|x| x.eq_ignore_ascii_case(&t)))
}

/// The size of a saved object's local variables (SWVarTable): KotOR 1 keeps 3 DWORDs of
/// booleans and 8 number bytes, KotOR 2 5 DWORDs and 32 bytes (read from a KotOR 2 save,
/// 2026-10-23). Set by played_through for the game it builds for.
pub fn var_layout(game: crate::games::Game) -> (usize, usize) {
    if game == crate::games::Game::K2 { (5, 32) } else { (3, 8) }
}

thread_local! {
    static LAYOUT: std::cell::Cell<(usize, usize)> = const { std::cell::Cell::new((3, 8)) };
}

/// An SWVarTable with the given boolean bits set: BitArray of DWORDs, ByteArray of BYTEs, as
/// every saved object carries it (SetLocalBoolean index i is bit i of the array).
fn swvartable_with(bits: &[u32], numbers: &[(u32, i64)]) -> Struct {
    let (nwords, nbytes) = LAYOUT.with(|l| l.get());
    let mut words = vec![0u32; nwords];
    for &b in bits {
        if (b as usize) < nwords * 32 {
            words[(b / 32) as usize] |= 1 << (b % 32);
        }
    }
    let mut t = Struct::new(0);
    let element = |label: &str, v: Value| {
        let mut e = Struct::new(0);
        e.set(label, v);
        e
    };
    t.set("BitArray", Value::List(words.iter().map(|w| element("Variable", Value::Dword(*w))).collect()));
    let mut bytes = vec![0u8; nbytes];
    for &(i, n) in numbers {
        if (i as usize) < nbytes {
            bytes[i as usize] = n.clamp(0, 255) as u8;
        }
    }
    t.set("ByteArray", Value::List(bytes.iter().map(|b| element("Variable", Value::Byte(*b))).collect()));
    t
}

/// Sets one local variable on a saved object, area or module (its SWVarTable, created in the
/// game's layout when missing): a boolean bit, or a number byte.
pub fn set_local(s: &mut Struct, game: crate::games::Game, number: bool, index: u32, value: i64) {
    let (nwords, nbytes) = var_layout(game);
    if s.get("SWVarTable").is_none() {
        LAYOUT.with(|l| l.set((nwords, nbytes)));
        s.set("SWVarTable", Value::Struct(swvartable_with(&[], &[])));
    }
    let Some(Value::Struct(t)) = s.get_mut("SWVarTable") else { return };
    let (list, len) = if number { ("ByteArray", nbytes) } else { ("BitArray", nwords) };
    if t.list(list).map_or(true, |l| l.len() < len) {
        let mut cur = t.list(list).cloned().unwrap_or_default();
        while cur.len() < len {
            let mut e = Struct::new(0);
            e.set("Variable", if number { Value::Byte(0) } else { Value::Dword(0) });
            cur.push(e);
        }
        t.set(list, Value::List(cur));
    }
    let l = t.list_mut(list).unwrap();
    if number {
        if (index as usize) < nbytes {
            l[index as usize].set("Variable", Value::Byte(value.clamp(0, 255) as u8));
        }
    } else if (index as usize) < nwords * 32 {
        let w = &mut l[(index / 32) as usize];
        let now = w.int("Variable").unwrap_or(0) as u32;
        let bit = 1u32 << (index % 32);
        w.set("Variable", Value::Dword(if value != 0 { now | bit } else { now & !bit }));
    }
}

/// The fields every saved door, placeable and trigger carries for its state.
fn object_state(s: &mut Struct, bits: &[u32]) {
    object_state_with(s, bits, &[]);
}


fn object_state_with(s: &mut Struct, bits: &[u32], numbers: &[(u32, i64)]) {
    s.set("VarTable", Value::List(Vec::new()));
    s.set("SWVarTable", Value::Struct(swvartable_with(bits, numbers)));
    s.set("ActionList", Value::List(Vec::new()));
    s.set("Commandable", Value::Byte(1));
}

/// A template's root fields, from the module's own files first, then Override and the
/// game's archives, as the game looks templates up.
fn template(files: &ModuleFiles, data: &GameData, resref: &str, ext: &str, kind: u16) -> Option<Struct> {
    files
        .read(resref, kind)
        .and_then(|d| Gff::read(&d).ok())
        .or_else(|| data.gff(resref, ext, kind))
        .map(|g| g.root)
}

/// The template made into a full struct of `id`, with the listed fields of the game .git
/// entry laid over it.
fn full(mut t: Struct, id: u32, entry: &Struct, instance: &[&str]) -> Struct {
    t.id = id;
    for label in ["TemplateResRef", "PaletteID", "Comment", "TemplateList"] {
        t.fields.retain(|(l, _)| l != label);
    }
    for label in instance {
        if let Some(v) = entry.get(label) {
            t.set(label, v.clone());
        }
    }
    t
}

/// The stored copy of `module` in its played-through state, as an ERF, or None when the
/// game's files for it are not there. `last_ifo` is the module.ifo of the area the save
/// resumes in: the live counters are taken from it, as a real stored copy would have them.
pub fn played_through(data: &GameData, module: &str, cleared: &Cleared, last_ifo: &Struct, base: &crate::formats::erf::Erf) -> Option<Vec<u8>> {
    LAYOUT.with(|l| l.set(var_layout(data.game)));
    use crate::formats::erf::{Erf, Resource, RES_TYPE_ARE, RES_TYPE_GIT, RES_TYPE_IFO};
    let files = ModuleFiles::open(&data.root, module);
    let ifo_game = Gff::read(&files.read("module", RES_TYPE_IFO)?).ok()?;
    let area = ifo_game.root.list("Mod_Area_list")?.first()?.string("Area_Name")?;
    let are = files.read(&area, RES_TYPE_ARE)?;
    let git_game = Gff::read(&files.read(&area, RES_TYPE_GIT)?).ok()?;
    let g = &git_game.root;

    // Object ids from 2 (the area is 1), unique over every list.
    let mut next_id = 2u32;
    let mut id = || {
        let v = next_id;
        next_id += 1;
        v
    };
    let entries = |list: &str| g.list(list).cloned().unwrap_or_default();
    let mut git = Struct::new(u32::MAX);

    // Creatures: every one still there after a full run, its spawn script still to run.
    let mut creatures = Vec::new();
    for e in entries("Creature List") {
        let Some(resref) = e.string("TemplateResRef") else { continue };
        let Some(t) = template(&files, data, &resref, "utc", 2027) else { continue };
        if tag_in(&t, &cleared.remove) {
            continue;
        }
        let mut c = crate::area::creature_from_template(&t, None);
        c.id = 4;
        crate::area::set_position(&mut c, crate::area::position(&e));
        for label in ["XOrientation", "YOrientation", "ZOrientation"] {
            if let Some(v) = e.get(label) {
                c.set(label, v.clone());
            }
        }
        c.set("ObjectId", Value::Dword(id()));
        c.set("AreaId", Value::Dword(1));
        let (bits, numbers) = locals_of(&c, cleared);
        c.set("SWVarTable", Value::Struct(swvartable_with(&bits, &numbers)));
        creatures.push(c);
    }

    // Doors: open and unlocked where a full run leaves them so.
    let mut doors = Vec::new();
    for e in entries("Door List") {
        let Some(resref) = e.string("TemplateResRef") else { continue };
        let Some(t) = template(&files, data, &resref, "utd", 2042) else { continue };
        let mut d = full(t, 8, &e, &["Bearing", "X", "Y", "Z", "LinkedTo", "LinkedToFlags", "LinkedToModule", "TransitionDestin"]);
        d.set("ObjectId", Value::Dword(id()));
        if tag_in(&d, &cleared.open) {
            d.set_int("OpenState", 1, Value::Byte(0));
        } else if d.get("OpenState").is_none() {
            d.set("OpenState", Value::Byte(0));
        }
        if tag_in(&d, &cleared.open) || tag_in(&d, &cleared.unlock) {
            d.set_int("Locked", 0, Value::Byte(0));
        }
        let hp = d.int("HP").unwrap_or(0);
        if d.int("CurrentHP").map_or(false, |c| c > hp) {
            d.set_int("CurrentHP", hp, Value::Short(0));
        }
        let (bits, numbers) = locals_of(&d, cleared);
        object_state_with(&mut d, &bits, &numbers);
        doors.push(d);
    }

    // Placeables: picked up or destroyed ones gone; looted containers empty.
    let mut placeables = Vec::new();
    for e in entries("Placeable List") {
        let Some(resref) = e.string("TemplateResRef") else { continue };
        let Some(t) = template(&files, data, &resref, "utp", 2044) else { continue };
        if tag_in(&t, &cleared.remove) {
            continue;
        }
        let mut p = full(t, 9, &e, &["Bearing", "X", "Y", "Z"]);
        p.set("ObjectId", Value::Dword(id()));
        p.set("Open", Value::Byte(0));
        let animation = match p.int("AnimationState").unwrap_or(0) {
            1 => 10075,
            2 => 10076,
            3 => 10074,
            4 => 10073,
            _ => 10000,
        };
        p.set("Animation", Value::Int(animation));
        if tag_in(&p, &cleared.looted) {
            p.set("ItemList", Value::List(Vec::new()));
            p.set_int("Locked", 0, Value::Byte(0));
        }
        if p.get("Static").is_some() {
            p.set_int("Static", 0, Value::Byte(0));
        }
        let (bits, numbers) = locals_of(&p, cleared);
        object_state_with(&mut p, &bits, &numbers);
        placeables.push(p);
    }

    // Triggers: their geometry and links from the .git, their fired bits from the run.
    let mut triggers = Vec::new();
    for e in entries("TriggerList") {
        let Some(resref) = e.string("TemplateResRef") else { continue };
        let Some(t) = template(&files, data, &resref, "utt", 2032) else { continue };
        let mut tr = full(
            t,
            1,
            &e,
            &["XPosition", "YPosition", "ZPosition", "XOrientation", "YOrientation", "ZOrientation", "Geometry", "LinkedTo", "LinkedToFlags", "LinkedToModule", "TransitionDestin"],
        );
        tr.set("ObjectId", Value::Dword(id()));
        tr.set("CreatorId", Value::Dword(0x7F00_0000));
        tr.set("SetByPlayerParty", Value::Byte(0));
        let (bits, numbers) = locals_of(&tr, cleared);
        object_state_with(&mut tr, &bits, &numbers);
        triggers.push(tr);
    }

    // Sounds, stores, encounters: the template and the .git's instance fields.
    let mut sounds = Vec::new();
    for e in entries("SoundList") {
        let Some(resref) = e.string("TemplateResRef") else { continue };
        let Some(t) = template(&files, data, &resref, "uts", 2035) else { continue };
        let mut so = full(t, 6, &e, &["GeneratedType", "XPosition", "YPosition", "ZPosition"]);
        so.set("ObjectId", Value::Dword(id()));
        so.set("FixedVariance", Value::Float(1.0));
        object_state(&mut so, &[]);
        sounds.push(so);
    }
    let mut stores = Vec::new();
    for e in entries("StoreList") {
        let Some(resref) = e.string("ResRef").or_else(|| e.string("TemplateResRef")) else { continue };
        let Some(t) = template(&files, data, &resref, "utm", 2051) else { continue };
        let mut st = full(t, 11, &e, &["XPosition", "YPosition", "ZPosition", "XOrientation", "YOrientation"]);
        st.set("ObjectId", Value::Dword(id()));
        stores.push(st);
    }
    let mut encounters = Vec::new();
    for e in entries("Encounter List") {
        let Some(resref) = e.string("TemplateResRef") else { continue };
        let Some(t) = template(&files, data, &resref, "ute", 2040) else { continue };
        let mut en = full(t, 7, &e, &["XPosition", "YPosition", "ZPosition", "Geometry", "SpawnPointList"]);
        en.set("ObjectId", Value::Dword(id()));
        en.set("NumberSpawned", Value::Int(0));
        en.set("Started", Value::Byte(0));
        en.set("CurrentSpawns", Value::Int(0));
        en.set("LastEntered", Value::Dword(0x7F00_0000));
        if tag_in(&en, &cleared.exhausted) {
            en.set("Exhausted", Value::Byte(1));
        }
        object_state(&mut en, &[]);
        encounters.push(en);
    }
    let mut waypoints = Vec::new();
    for mut w in entries("WaypointList") {
        // Already full in the game's .git; a stored copy adds its id and state.
        w.id = 5;
        w.set("ObjectId", Value::Dword(id()));
        object_state(&mut w, &[]);
        waypoints.push(w);
    }

    git.set("AreaProperties", g.get("AreaProperties").cloned().unwrap_or(Value::Struct(Struct::new(100))));
    git.set("Creature List", Value::List(creatures));
    git.set("Door List", Value::List(doors));
    git.set("Placeable List", Value::List(placeables));
    git.set("TriggerList", Value::List(triggers));
    git.set("SoundList", Value::List(sounds));
    git.set("StoreList", Value::List(stores));
    git.set("Encounter List", Value::List(encounters));
    git.set("WaypointList", Value::List(waypoints));
    git.set("CameraList", g.get("CameraList").cloned().unwrap_or(Value::List(Vec::new())));
    git.set("List", Value::List(Vec::new()));
    git.set("AreaEffectList", Value::List(Vec::new()));
    git.set("VarTable", Value::List(Vec::new()));
    git.set("SWVarTable", Value::Struct(swvartable_with(&cleared.area_bits, &cleared.area_numbers)));
    git.set("CurrentWeather", Value::Byte(0));
    git.set("WeatherStarted", Value::Byte(0));
    git.set("TransPending", Value::Byte(0));
    git.set("TransPendNextID", Value::Byte(0));
    git.set("TransPendCurrID", Value::Byte(0));

    // module.ifo: the game's, as a saved module, the live counters from the save.
    let mut ifo = ifo_game.root.clone();
    ifo.set("Mod_IsSaveGame", Value::Byte(1));
    ifo.set("Mod_IsNWMFile", Value::Byte(0));
    if let Some(Value::List(areas)) = ifo.get_mut("Mod_Area_list") {
        if let Some(a) = areas.first_mut() {
            a.set("ObjectId", Value::Dword(1));
        }
    }
    ifo.set("Mod_NextObjId0", Value::Dword(next_id + 50));
    ifo.set("Mod_NextObjId1", Value::Dword(0));
    for label in ["Mod_NextCharId0", "Mod_NextCharId1", "Mod_Effect_NxtId", "Mod_PauseDay", "Mod_PauseTime", "Mod_StartYear", "Mod_StartMonth", "Mod_StartDay", "Mod_StartHour", "Mod_StartMinute", "Mod_StartSecond", "Mod_StartMiliSec", "Mod_Transition"] {
        if let Some(v) = last_ifo.get(label) {
            ifo.set(label, v.clone());
        }
    }
    ifo.set("VarTable", Value::List(Vec::new()));
    ifo.set("SWVarTable", Value::Struct(swvartable_with(&cleared.module_bits, &cleared.module_numbers)));
    ifo.set("EventQueue", Value::List(Vec::new()));
    ifo.set("Mod_Tokens", Value::List(Vec::new()));
    ifo.set("Creature List", Value::List(Vec::new()));
    // The player as a real copy keeps it (not read on a trip in), at the area's entry.
    if let Some(mut pc) = last_ifo.list("Mod_PlayerList").and_then(|l| l.first()).cloned() {
        pc.set("AreaId", Value::Dword(1));
        for (from, to) in [("Mod_Entry_X", "XPosition"), ("Mod_Entry_Y", "YPosition"), ("Mod_Entry_Z", "ZPosition")] {
            if let Some(v) = ifo.get(from).cloned() {
                pc.set(to, v);
            }
        }
        ifo.set("Mod_PlayerList", Value::List(vec![pc]));
    }
    for label in ["Expansion_Pack", "Mod_GVar_List", "Mod_StartMovie", "Mod_VO_ID"] {
        ifo.fields.retain(|(l, _)| l != label);
    }

    let mut erf = Erf { resources: Vec::new(), ..base.clone() };
    erf.resources.push(Resource { name: "module".into(), kind: RES_TYPE_IFO, id: 0, data: Gff { file_type: *b"IFO ", root: ifo }.write() });
    erf.resources.push(Resource { name: area.to_ascii_lowercase(), kind: RES_TYPE_ARE, id: 1, data: are });
    erf.resources.push(Resource { name: area.to_ascii_lowercase(), kind: RES_TYPE_GIT, id: 2, data: Gff { file_type: *b"GIT ", root: git }.write() });
    Some(erf.write())
}
