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
