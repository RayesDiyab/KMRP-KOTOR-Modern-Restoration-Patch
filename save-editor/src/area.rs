//! The current area as the save left it (its .git): doors, containers, stores and the
//! creatures standing there. Changing a lock or a container's contents here is what the
//! game finds when the save loads.

use crate::formats::gff::{Struct, Value};

pub const DOORS: &str = "Door List";
pub const PLACEABLES: &str = "Placeable List";
pub const STORES: &str = "StoreList";
pub const CREATURES: &str = "Creature List";

#[derive(Clone, Debug)]
pub struct Door {
    pub index: usize,
    pub tag: String,
    pub locked: bool,
    pub open: bool,
    pub key_required: bool,
    pub key: String,
    pub lock_dc: i64,
    pub plot: bool,
}

pub fn doors(git: &Struct) -> Vec<Door> {
    git.list(DOORS)
        .map(|l| {
            l.iter()
                .enumerate()
                .map(|(index, d)| Door {
                    index,
                    tag: d.string("Tag").unwrap_or_default(),
                    locked: d.int("Locked") == Some(1),
                    open: d.int("OpenState").unwrap_or(0) != 0,
                    key_required: d.int("KeyRequired") == Some(1),
                    key: d.string("KeyName").unwrap_or_default(),
                    lock_dc: d.int("OpenLockDC").unwrap_or(0),
                    plot: d.int("Plot") == Some(1),
                })
                .collect()
        })
        .unwrap_or_default()
}

pub fn set_door_locked(git: &mut Struct, index: usize, locked: bool) {
    if let Some(d) = git.list_mut(DOORS).and_then(|l| l.get_mut(index)) {
        d.set_int("Locked", locked as i64, Value::Byte(0));
        if !locked {
            // A door that only its key opens would stay shut to Security too.
            d.set_int("KeyRequired", 0, Value::Byte(0));
        }
    }
}

pub fn set_door_open(git: &mut Struct, index: usize, open: bool) {
    if let Some(d) = git.list_mut(DOORS).and_then(|l| l.get_mut(index)) {
        d.set_int("OpenState", open as i64, Value::Byte(0));
        if open {
            d.set_int("Locked", 0, Value::Byte(0));
        }
    }
}

#[derive(Clone, Debug)]
pub struct Container {
    pub list: &'static str,
    pub index: usize,
    pub tag: String,
    pub name: String,
    pub items: usize,
    pub locked: bool,
}

/// Placeables that hold items, and stores.
pub fn containers(git: &Struct, name: &dyn Fn(&Struct) -> String) -> Vec<Container> {
    let mut out = Vec::new();
    for list in [PLACEABLES, STORES] {
        if let Some(l) = git.list(list) {
            for (index, p) in l.iter().enumerate() {
                let has = list == STORES || p.int("HasInventory") == Some(1) || p.list("ItemList").map_or(false, |i| !i.is_empty());
                if !has {
                    continue;
                }
                out.push(Container {
                    list,
                    index,
                    tag: p.string("Tag").unwrap_or_default(),
                    name: name(p),
                    items: p.list("ItemList").map_or(0, |i| i.len()),
                    locked: p.int("Locked") == Some(1),
                });
            }
        }
    }
    out
}

pub fn container_mut<'a>(git: &'a mut Struct, list: &str, index: usize) -> Option<&'a mut Struct> {
    git.list_mut(list)?.get_mut(index)
}

pub fn container<'a>(git: &'a Struct, list: &str, index: usize) -> Option<&'a Struct> {
    git.list(list)?.get(index)
}

/// Items in a container need object ids the area has not used; stores number their
/// items by position instead.
pub fn next_object_id(git: &Struct) -> u32 {
    fn walk(s: &Struct, max: &mut u32) {
        for (label, v) in &s.fields {
            match v {
                Value::Dword(id) if label == "ObjectId" && *id != u32::MAX && *id < 0x7F00_0000 => {
                    *max = (*max).max(*id)
                }
                Value::Struct(c) => walk(c, max),
                Value::List(l) => l.iter().for_each(|c| walk(c, max)),
                _ => {}
            }
        }
    }
    let mut max = 0;
    walk(git, &mut max);
    max + 1
}

/// The player's position in the area: XPosition/YPosition/ZPosition.
pub fn position(c: &Struct) -> [f32; 3] {
    [
        c.float("XPosition").unwrap_or(0.0),
        c.float("YPosition").unwrap_or(0.0),
        c.float("ZPosition").unwrap_or(0.0),
    ]
}

pub fn set_position(c: &mut Struct, p: [f32; 3]) {
    c.set_float("XPosition", p[0]);
    c.set_float("YPosition", p[1]);
    c.set_float("ZPosition", p[2]);
}

#[derive(Clone, Debug)]
pub struct Creature {
    pub index: usize,
    pub tag: String,
    pub name: String,
    pub hp: i64,
    pub max_hp: i64,
}

/// The creatures standing in the area as the save left them.
pub fn creatures(git: &Struct, name: &dyn Fn(&Struct) -> String) -> Vec<Creature> {
    git.list(CREATURES)
        .map(|l| {
            l.iter()
                .enumerate()
                .map(|(index, c)| {
                    let (hp, max_hp) = crate::creature::health(c);
                    Creature { index, tag: c.string("Tag").unwrap_or_default(), name: name(c), hp, max_hp }
                })
                .collect()
        })
        .unwrap_or_default()
}

pub fn creature_mut<'a>(git: &'a mut Struct, index: usize) -> Option<&'a mut Struct> {
    git.list_mut(CREATURES)?.get_mut(index)
}

pub fn remove_creature(git: &mut Struct, index: usize) {
    if let Some(l) = git.list_mut(CREATURES) {
        if index < l.len() {
            l.remove(index);
        }
    }
}

// ---- spawning ----
//
// How the game loads a creature from a saved area (the maintainer's own reverse
// engineering of KotOR 1, 1.0.3; save-editor-format.md, "Spawning"): a saved .git has no
// UseTemplates, so every Creature List entry is read in full, never from a template. Its
// ObjectId is kept (a fresh one from Module.ifo's Mod_NextObjId0 when it is absent);
// everything the area keeps beyond a template (perception, actions, effects, combat round,
// local variables) is optional and starts empty. CreatnScrptFird is the "spawn script
// fired" flag: at 0 the game runs the creature's OnSpawn script itself, on its first AI
// update after the save loads.

/// The fields only the toolset uses; a saved creature has none of them.
const TEMPLATE_ONLY: [&str; 4] = ["TemplateResRef", "Comment", "PaletteID", "TemplateList"];

/// Lists that hold what the creature was doing, seeing and carrying as effects: a new
/// creature starts with them empty.
const RUNTIME_LISTS: [&str; 4] = ["PerceptionList", "ActionList", "EffectList", "ExpressionList"];

/// A creature already standing in the area, copied: the same person with the same state
/// (its spawn script has run), but nothing it was doing, seeing or under. The ids are the
/// caller's to give.
pub fn copy_creature(source: &Struct) -> Struct {
    let mut c = source.clone();
    for list in RUNTIME_LISTS {
        if list != "ExpressionList" && c.get(list).is_some() {
            c.set(list, Value::List(Vec::new()));
        }
    }
    c.fields.retain(|(label, _)| label != "FollowInfo" && label != "CombatRoundData" && label != "CombatInfo");
    c
}

/// A creature template (.utc) made into a creature as a saved area holds it, its spawn
/// script still to run. `like` is a creature already in the area: the save-only fields the
/// template lacks take its shape (field kinds, AreaId), else the game's defaults.
pub fn creature_from_template(template: &Struct, like: Option<&Struct>) -> Struct {
    let mut c = Struct::new(4);
    for (label, value) in &template.fields {
        if !TEMPLATE_ONLY.contains(&label.as_str()) {
            c.fields.push((label.clone(), value.clone()));
        }
    }
    let defaults: [(&str, Value); 16] = [
        ("DetectMode", Value::Byte(1)),
        ("StealthMode", Value::Byte(0)),
        // 0: the game takes the size from appearance.2da.
        ("CreatureSize", Value::Int(0)),
        ("IsDestroyable", Value::Byte(1)),
        ("IsRaiseable", Value::Byte(1)),
        ("DeadSelectable", Value::Byte(0)),
        ("AmbientAnimState", Value::Byte(0)),
        ("Animation", Value::Int(10000)),
        ("CreatnScrptFird", Value::Byte(0)),
        ("PM_IsDisguised", Value::Byte(0)),
        ("Listening", Value::Byte(0)),
        ("JoiningXP", Value::Dword(0)),
        ("Commandable", Value::Byte(1)),
        ("AIState", Value::Int(0)),
        ("MovementRate", Value::Byte(4)),
        ("Gold", Value::Dword(0)),
    ];
    for (label, value) in defaults {
        if c.get(label).is_none() {
            // The donor's kind of value, with the default's number.
            let v = like
                .and_then(|l| l.get(label))
                .and_then(|kind| kind.with_int(value.as_int().unwrap_or(0)))
                .unwrap_or(value);
            c.fields.push((label.to_string(), v));
        }
    }
    // The spawn script has not run, whatever the donor says.
    c.set_int("CreatnScrptFird", 0, Value::Byte(0));
    if let Some(area) = like.and_then(|l| l.get("AreaId")).cloned() {
        c.set("AreaId", area);
    }
    for list in RUNTIME_LISTS.iter().chain(["VarTable"].iter()) {
        if c.get(list).is_none() {
            c.fields.push((list.to_string(), Value::List(Vec::new())));
        }
    }
    // The script variables: the donor's table with every value zeroed, so the shape is the
    // game's own.
    if let (None, Some(Value::Struct(table))) = (c.get("SWVarTable"), like.and_then(|l| l.get("SWVarTable"))) {
        let mut t = table.clone();
        zero(&mut t);
        c.fields.push(("SWVarTable".into(), Value::Struct(t)));
    }
    for (label, value) in [("XOrientation", 1.0f32), ("YOrientation", 0.0), ("ZOrientation", 0.0)] {
        if c.get(label).is_none() {
            c.fields.push((label.to_string(), Value::Float(value)));
        }
    }
    for label in ["XPosition", "YPosition", "ZPosition"] {
        if c.get(label).is_none() {
            c.fields.push((label.to_string(), Value::Float(0.0)));
        }
    }
    c
}

fn zero(s: &mut Struct) {
    for (_, v) in s.fields.iter_mut() {
        match v {
            Value::Struct(c) => zero(c),
            Value::List(l) => l.iter_mut().for_each(zero),
            other => {
                if let Some(z) = other.with_int(0) {
                    *other = z;
                }
            }
        }
    }
}

/// Places a creature: position and the way it faces (an angle in radians).
pub fn place_creature(c: &mut Struct, pos: [f32; 3], facing: f32) {
    set_position(c, pos);
    c.set_float("XOrientation", facing.cos());
    c.set_float("YOrientation", facing.sin());
    c.set_float("ZOrientation", 0.0);
}

/// The items a creature carries as full items (each with its own ObjectId), worn and in
/// its pack; template-style entries (EquippedRes, InventoryRes) have no id and are left.
pub fn creature_items_mut(c: &mut Struct) -> Vec<&mut Struct> {
    let mut out = Vec::new();
    for (label, v) in c.fields.iter_mut() {
        if label == "Equip_ItemList" || label == "ItemList" {
            if let Value::List(l) = v {
                out.extend(l.iter_mut().filter(|i| i.get("ObjectId").is_some()));
            }
        }
    }
    out
}

pub fn add_creature(git: &mut Struct, c: Struct) {
    if git.list(CREATURES).is_none() {
        git.set(CREATURES, Value::List(Vec::new()));
    }
    git.list_mut(CREATURES).unwrap().push(c);
}
