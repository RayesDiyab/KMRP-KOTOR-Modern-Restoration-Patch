//! Reading and changing one creature (the player or a party member) as the game stores
//! it in a save. Every change keeps the game's own field types and list shapes: a new
//! list entry is cloned from one already there, so KotOR 2's extra fields come along.

use crate::formats::gff::{LocString, Struct, Value};

pub const ATTRIBUTES: [&str; 6] = ["Str", "Dex", "Con", "Int", "Wis", "Cha"];

pub fn modifier(score: i64) -> i64 {
    (score - 10).div_euclid(2)
}

pub fn name(c: &Struct) -> String {
    let first = match c.get("FirstName") {
        Some(Value::LocString(l)) => l.strings.first().map(|(_, t)| crate::text::decode(t)),
        _ => None,
    };
    let last = match c.get("LastName") {
        Some(Value::LocString(l)) => l.strings.first().map(|(_, t)| crate::text::decode(t)),
        _ => None,
    };
    let mut n = first.unwrap_or_default();
    if let Some(l) = last.filter(|l| !l.is_empty()) {
        n = format!("{} {}", n, l);
    }
    n.trim().to_string()
}

/// The player's name lives in FirstName (and Mod_FirstName); the last name is cleared,
/// as character creation leaves it.
pub fn set_name(c: &mut Struct, text: &str) {
    let bytes = crate::text::encode(text);
    for label in ["FirstName", "Mod_FirstName"] {
        if let Some(Value::LocString(l)) = c.get_mut(label) {
            l.strref = u32::MAX;
            if l.strings.is_empty() {
                l.strings.push((0, bytes.clone()));
            } else {
                for s in l.strings.iter_mut() {
                    s.1 = bytes.clone();
                }
            }
        }
    }
    for label in ["LastName", "Mod_LastName"] {
        if let Some(Value::LocString(l)) = c.get_mut(label) {
            *l = LocString { strref: u32::MAX, strings: Vec::new() };
        }
    }
}

pub fn attribute(c: &Struct, label: &str) -> i64 {
    c.int(label).unwrap_or(10)
}

pub fn set_attribute(c: &mut Struct, label: &str, value: i64) {
    c.set_int(label, value.clamp(1, 100), Value::Byte(0));
}

pub fn skill(c: &Struct, index: usize) -> i64 {
    c.list("SkillList").and_then(|l| l.get(index)).and_then(|s| s.int("Rank")).unwrap_or(0)
}

pub fn set_skill(c: &mut Struct, index: usize, rank: i64) {
    if let Some(list) = c.list_mut("SkillList") {
        if let Some(s) = list.get_mut(index) {
            s.set_int("Rank", rank.clamp(0, 99), Value::Byte(0));
        }
    }
}

pub fn classes(c: &Struct) -> Vec<(i64, i64)> {
    c.list("ClassList")
        .map(|l| l.iter().map(|e| (e.int("Class").unwrap_or(0), e.int("ClassLevel").unwrap_or(0))).collect())
        .unwrap_or_default()
}

pub fn level(c: &Struct) -> i64 {
    classes(c).iter().map(|(_, l)| l).sum()
}

pub fn feats(c: &Struct) -> Vec<i64> {
    c.list("FeatList").map(|l| l.iter().filter_map(|f| f.int("Feat")).collect()).unwrap_or_default()
}

/// Appends a list entry shaped like the entries already in the list (or `fallback`),
/// with `field` set to `value`.
fn push_like(list: &mut Vec<Struct>, field: &str, value: i64, fallback: Struct) {
    let mut entry = list.first().cloned().unwrap_or(fallback);
    entry.set_int(field, value, Value::Word(0));
    list.push(entry);
}

pub fn add_feat(c: &mut Struct, feat: i64) -> bool {
    if feats(c).contains(&feat) {
        return false;
    }
    if c.list("FeatList").is_none() {
        c.set("FeatList", Value::List(Vec::new()));
    }
    let mut fallback = Struct::new(1);
    fallback.set("Feat", Value::Word(0));
    push_like(c.list_mut("FeatList").unwrap(), "Feat", feat, fallback);
    true
}

/// Removes this one feat: from the creature's list and from the level record that gave
/// it (the player's LvlStatList), nothing else.
pub fn remove_feat(c: &mut Struct, feat: i64) -> bool {
    let mut removed = false;
    if let Some(list) = c.list_mut("FeatList") {
        let before = list.len();
        list.retain(|f| f.int("Feat") != Some(feat));
        removed = list.len() != before;
    }
    if let Some(levels) = c.list_mut("LvlStatList") {
        for l in levels.iter_mut() {
            if let Some(list) = l.list_mut("FeatList") {
                list.retain(|f| f.int("Feat") != Some(feat));
            }
        }
    }
    removed
}

/// The Force powers a creature knows, from every class's KnownList0.
pub fn powers(c: &Struct) -> Vec<i64> {
    let mut out = Vec::new();
    if let Some(classes) = c.list("ClassList") {
        for class in classes {
            if let Some(list) = class.list("KnownList0") {
                out.extend(list.iter().filter_map(|s| s.int("Spell")));
            }
        }
    }
    out
}

/// Which ClassList entry holds Force powers: the one that already has some, else the
/// first Force-using class (`is_force_class` from classes.2da).
fn power_class(c: &Struct, is_force_class: &dyn Fn(i64) -> bool) -> Option<usize> {
    let classes = c.list("ClassList")?;
    classes
        .iter()
        .position(|e| e.list("KnownList0").map_or(false, |l| !l.is_empty()))
        .or_else(|| classes.iter().position(|e| is_force_class(e.int("Class").unwrap_or(-1))))
}

pub fn can_have_powers(c: &Struct, is_force_class: &dyn Fn(i64) -> bool) -> bool {
    power_class(c, is_force_class).is_some()
}

pub fn add_power(c: &mut Struct, spell: i64, is_force_class: &dyn Fn(i64) -> bool) -> bool {
    if powers(c).contains(&spell) {
        return false;
    }
    let Some(index) = power_class(c, is_force_class) else { return false };
    let class = &mut c.list_mut("ClassList").unwrap()[index];
    if class.list("KnownList0").is_none() {
        class.set("KnownList0", Value::List(Vec::new()));
    }
    let mut fallback = Struct::new(3);
    fallback.set("Spell", Value::Word(0));
    push_like(class.list_mut("KnownList0").unwrap(), "Spell", spell, fallback);
    true
}

/// Removes exactly this power (KSE removed every power at once in KotOR 2).
pub fn remove_power(c: &mut Struct, spell: i64) -> bool {
    let mut removed = false;
    if let Some(classes) = c.list_mut("ClassList") {
        for class in classes.iter_mut() {
            if let Some(list) = class.list_mut("KnownList0") {
                let before = list.len();
                list.retain(|s| s.int("Spell") != Some(spell));
                removed |= list.len() != before;
            }
        }
    }
    if let Some(levels) = c.list_mut("LvlStatList") {
        for l in levels.iter_mut() {
            if let Some(list) = l.list_mut("KnownList0") {
                list.retain(|s| s.int("Spell") != Some(spell));
            }
        }
    }
    removed
}

/// Health as the game will show it: (current, maximum). The save keeps the current
/// value relative to the base (HitPoints), and the maximum as written at save time.
pub fn health(c: &Struct) -> (i64, i64) {
    let base = c.int("HitPoints").unwrap_or(0);
    let max = c.int("MaxHitPoints").unwrap_or(base);
    let current = c.int("CurrentHitPoints").unwrap_or(base) + (max - base);
    (current, max)
}

pub fn force(c: &Struct) -> (i64, i64) {
    let base = c.int("ForcePoints").unwrap_or(0);
    let max = c.int("MaxForcePoints").unwrap_or(base);
    let current = c.int("CurrentForce").unwrap_or(base) + (max - base);
    (current, max)
}

/// Full health and Force: the stored current value equal to the stored base, which the
/// game raises by the same bonus as the maximum when it loads.
pub fn heal(c: &mut Struct) {
    if let Some(base) = c.int("HitPoints") {
        c.set_int("CurrentHitPoints", base, Value::Short(0));
    }
    if let Some(base) = c.int("ForcePoints") {
        c.set_int("CurrentForce", base, Value::Short(0));
    }
}

pub fn experience(c: &Struct) -> i64 {
    c.int("Experience").unwrap_or(0)
}

pub fn set_experience(c: &mut Struct, xp: i64) {
    c.set_int("Experience", xp.max(0), Value::Dword(0));
}

pub fn alignment(c: &Struct) -> i64 {
    c.int("GoodEvil").unwrap_or(50)
}

pub fn set_alignment(c: &mut Struct, value: i64) {
    c.set_int("GoodEvil", value.clamp(0, 100), Value::Byte(0));
}

/// A second class at level 1, the way a level-up into it would leave the creature: the
/// class entry, its hit die (and Force die) added to the base Health (and Force), and
/// for the player a level record, without which the game's Health sum runs past the
/// end of the list. The game recognises two classes at most.
pub fn add_class(c: &mut Struct, class: &crate::catalog::Class, xp_needed: Option<i64>) -> bool {
    let Some(list) = c.list("ClassList") else { return false };
    if list.len() >= 2 || list.iter().any(|e| e.int("Class") == Some(class.id)) {
        return false;
    }
    let force_template = list.iter().find(|e| e.list("KnownList0").is_some()).cloned();
    let mut entry = list[0].clone();
    entry.fields.retain(|(l, _)| l != "KnownList0" && l != "SpellsPerDayList");
    entry.set_int("Class", class.id, Value::Int(0));
    entry.set_int("ClassLevel", 1, Value::Short(0));
    if class.force_die > 0 {
        match force_template {
            Some(t) => {
                if let Some(v) = t.get("SpellsPerDayList") {
                    entry.set("SpellsPerDayList", v.clone());
                }
                entry.set("KnownList0", Value::List(Vec::new()));
            }
            None => {
                let mut left = Struct::new(17767);
                left.set("NumSpellsLeft", Value::Byte(0));
                entry.set("SpellsPerDayList", Value::List(vec![left]));
                entry.set("KnownList0", Value::List(Vec::new()));
            }
        }
    }
    c.list_mut("ClassList").unwrap().push(entry);
    let hp = c.int("HitPoints").unwrap_or(0) + class.hit_die;
    c.set_int("HitPoints", hp, Value::Short(0));
    let cur = c.int("CurrentHitPoints").unwrap_or(0) + class.hit_die;
    c.set_int("CurrentHitPoints", cur, Value::Short(0));
    if class.force_die > 0 {
        let fp = c.int("ForcePoints").unwrap_or(0) + class.force_die;
        c.set_int("ForcePoints", fp, Value::Short(0));
        let cf = c.int("CurrentForce").unwrap_or(0) + class.force_die;
        c.set_int("CurrentForce", cf, Value::Short(0));
    }
    if let Some(levels) = c.list_mut("LvlStatList") {
        let mut record = levels.last().cloned().unwrap_or_else(|| Struct::new(0));
        record.fields.retain(|(l, _)| l != "LvlStatAbility");
        record.set_int("LvlStatHitDie", class.hit_die, Value::Byte(0));
        record.set_int("LvlStatForce", class.force_die, Value::Byte(0));
        record.set_int("LvlStatClass", class.id, Value::Byte(0));
        record.set_int("SkillPoints", 0, Value::Word(0));
        if let Some(skills) = record.list_mut("SkillList") {
            for s in skills.iter_mut() {
                s.set_int("Rank", 0, Value::Byte(0));
            }
        }
        for l in ["FeatList", "KnownList0"] {
            if record.get(l).is_some() {
                record.set(l, Value::List(Vec::new()));
            }
        }
        levels.push(record);
    }
    if let Some(need) = xp_needed {
        if experience(c) < need {
            set_experience(c, need);
        }
    }
    true
}

/// A new portrait, with the body that goes with it in the same build (small, medium,
/// large) as the current one, and the matching gender.
pub fn set_look(c: &mut Struct, portrait: &crate::catalog::Portrait, current: Option<&crate::catalog::Portrait>) {
    let appearance = c.int("Appearance_Type").unwrap_or(0);
    let build = current.and_then(|p| p.bodies.iter().position(|&b| b == appearance)).unwrap_or(1);
    c.set_int("PortraitId", portrait.id, Value::Word(0));
    c.set_int("Appearance_Type", portrait.bodies[build], Value::Word(0));
    c.set_int("Gender", portrait.female as i64, Value::Byte(0));
}

pub fn equipped(c: &Struct) -> Vec<&Struct> {
    c.list("Equip_ItemList").map(|l| l.iter().collect()).unwrap_or_default()
}
