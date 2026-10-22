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
    crate::text::strip_codes(&n)
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

// ---- what KSE also edits: look, voice, health, classes and levels, equipment ----

pub fn set_portrait(c: &mut Struct, id: i64) {
    c.set_int("PortraitId", id, Value::Word(0));
}

pub fn set_appearance(c: &mut Struct, id: i64) {
    c.set_int("Appearance_Type", id, Value::Word(0));
}

pub fn set_gender(c: &mut Struct, id: i64) {
    c.set_int("Gender", id, Value::Byte(0));
}

pub fn set_soundset(c: &mut Struct, id: i64) {
    c.set_int("SoundSetFile", id, Value::Word(0));
}

/// Health as the game shows it, set: the stored current value is relative to the base
/// (section 3.4 of save-editor-format.md), so the bonus on top is kept out of it.
pub fn set_current_health(c: &mut Struct, shown: i64) {
    let (_, max) = health(c);
    let base = c.int("HitPoints").unwrap_or(0);
    c.set_int("CurrentHitPoints", shown.min(max) - (max - base), Value::Short(0));
}

pub fn set_current_force(c: &mut Struct, shown: i64) {
    let (_, max) = force(c);
    let base = c.int("ForcePoints").unwrap_or(0);
    c.set_int("CurrentForce", shown.min(max) - (max - base), Value::Short(0));
}

/// The maximum Health: the game sums it from the player's level records, and from the
/// base for anyone else, so the difference goes to the last record (player) and to the
/// base (everyone), with the stored maximum and current value moved along.
pub fn set_max_health(c: &mut Struct, max: i64) {
    let (_, now) = health(c);
    let delta = max.max(1) - now;
    if delta == 0 {
        return;
    }
    for label in ["HitPoints", "MaxHitPoints", "CurrentHitPoints"] {
        if let Some(v) = c.int(label) {
            c.set_int(label, (v + delta).max(1), Value::Short(0));
        }
    }
    if let Some(levels) = c.list_mut("LvlStatList") {
        if let Some(last) = levels.last_mut() {
            let die = last.int("LvlStatHitDie").unwrap_or(0);
            last.set_int("LvlStatHitDie", (die + delta).clamp(1, 255), Value::Byte(0));
        }
    }
}

/// The maximum Force: base and stored maximum move together (the game adds Wisdom and
/// Charisma on top when the save loads).
pub fn set_max_force(c: &mut Struct, max: i64) {
    let (_, now) = force(c);
    let delta = max.max(0) - now;
    for label in ["ForcePoints", "MaxForcePoints", "CurrentForce"] {
        if let Some(v) = c.int(label) {
            c.set_int(label, (v + delta).max(0), Value::Short(0));
        }
    }
}

pub fn min1hp(c: &Struct) -> bool {
    c.int("Min1HP") == Some(1)
}

pub fn set_min1hp(c: &mut Struct, on: bool) {
    c.set_int("Min1HP", on as i64, Value::Byte(0));
}

/// A level record for one level of `class`, shaped like the records already there.
fn level_record(c: &Struct, class: &crate::catalog::Class) -> Struct {
    let mut record = c.list("LvlStatList").and_then(|l| l.last().cloned()).unwrap_or_else(|| Struct::new(0));
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
    record
}

fn add_to(c: &mut Struct, label: &str, delta: i64) {
    if let Some(v) = c.int(label) {
        c.set_int(label, (v + delta).max(0), Value::Short(0));
    }
}

/// Sets class entry `index` to `level`. Going up adds the class's hit die and Force die
/// per level, and for the player a level record each. Going down takes the player's
/// last records of that class away together with what they gave (feats, powers, skill
/// ranks, the raised attribute), as the game would never have granted them. Experience
/// moves to the first XP of the new total level when it no longer fits.
pub fn set_class_level(c: &mut Struct, index: usize, level_wanted: i64, class: &crate::catalog::Class, xp_for: &dyn Fn(i64) -> Option<i64>) {
    let Some(now) = c.list("ClassList").and_then(|l| l.get(index)).and_then(|e| e.int("ClassLevel")) else { return };
    let wanted = level_wanted.max(1);
    let delta = wanted - now;
    if delta == 0 {
        return;
    }
    if let Some(e) = c.list_mut("ClassList").and_then(|l| l.get_mut(index)) {
        e.set_int("ClassLevel", wanted, Value::Short(0));
    }
    add_to(c, "HitPoints", class.hit_die * delta);
    add_to(c, "CurrentHitPoints", class.hit_die * delta);
    add_to(c, "MaxHitPoints", class.hit_die * delta);
    if class.force_die > 0 {
        add_to(c, "ForcePoints", class.force_die * delta);
        add_to(c, "CurrentForce", class.force_die * delta);
        add_to(c, "MaxForcePoints", class.force_die * delta);
    }
    if c.list("LvlStatList").is_some() {
        if delta > 0 {
            for _ in 0..delta {
                let record = level_record(c, class);
                c.list_mut("LvlStatList").unwrap().push(record);
            }
        } else {
            for _ in 0..(-delta) {
                let levels = c.list("LvlStatList").unwrap();
                // The last record of that class; the last record when none names it (a
                // save another editor left with records that do not match its classes).
                let Some(pos) = levels.iter().rposition(|r| r.int("LvlStatClass") == Some(class.id)).or(levels.len().checked_sub(1)) else { break };
                let record = c.list_mut("LvlStatList").unwrap().remove(pos);
                undo_record(c, &record);
            }
        }
    }
    fit_experience(c, xp_for);
}

/// Experience within the current total level: raised to its first XP, or lowered when it
/// would already reach the next level.
fn fit_experience(c: &mut Struct, xp_for: &dyn Fn(i64) -> Option<i64>) {
    let total = level(c);
    let xp = experience(c);
    let low = xp_for(total).unwrap_or(0);
    let high = xp_for(total + 1);
    if xp < low || high.map_or(false, |h| xp >= h) {
        set_experience(c, low);
    }
}

/// Takes back what one level record gave.
fn undo_record(c: &mut Struct, record: &Struct) {
    let feats: Vec<i64> = record.list("FeatList").map(|l| l.iter().filter_map(|f| f.int("Feat")).collect()).unwrap_or_default();
    for f in feats {
        if let Some(list) = c.list_mut("FeatList") {
            list.retain(|x| x.int("Feat") != Some(f));
        }
    }
    let powers: Vec<i64> = record.list("KnownList0").map(|l| l.iter().filter_map(|s| s.int("Spell")).collect()).unwrap_or_default();
    for p in powers {
        if let Some(classes) = c.list_mut("ClassList") {
            for e in classes.iter_mut() {
                if let Some(list) = e.list_mut("KnownList0") {
                    list.retain(|s| s.int("Spell") != Some(p));
                }
            }
        }
    }
    let ranks: Vec<i64> = record.list("SkillList").map(|l| l.iter().map(|s| s.int("Rank").unwrap_or(0)).collect()).unwrap_or_default();
    for (i, r) in ranks.into_iter().enumerate() {
        if r > 0 {
            let now = skill(c, i);
            set_skill(c, i, now - r);
        }
    }
    if let Some(a) = record.int("LvlStatAbility") {
        if let Some(label) = ATTRIBUTES.get(a as usize) {
            let v = attribute(c, label);
            set_attribute(c, label, v - 1);
        }
    }
}

/// Changes class entry `index` to another class at the same level: the hit and Force
/// dice of its levels change with it; powers go when the new class has no Force, and a
/// Force class gets an empty power list.
pub fn change_class(c: &mut Struct, index: usize, old: &crate::catalog::Class, new: &crate::catalog::Class) {
    let Some(entry) = c.list("ClassList").and_then(|l| l.get(index)).cloned() else { return };
    if c.list("ClassList").unwrap().iter().any(|e| e.int("Class") == Some(new.id)) {
        return;
    }
    let levels = entry.int("ClassLevel").unwrap_or(1);
    {
        let e = &mut c.list_mut("ClassList").unwrap()[index];
        e.set_int("Class", new.id, Value::Int(0));
        if new.force_die > 0 {
            if e.get("KnownList0").is_none() {
                e.set("KnownList0", Value::List(Vec::new()));
            }
            if e.get("SpellsPerDayList").is_none() {
                let mut left = Struct::new(17767);
                left.set("NumSpellsLeft", Value::Byte(0));
                e.set("SpellsPerDayList", Value::List(vec![left]));
            }
        } else {
            e.fields.retain(|(l, _)| l != "KnownList0" && l != "SpellsPerDayList");
        }
    }
    let hp = (new.hit_die - old.hit_die) * levels;
    add_to(c, "HitPoints", hp);
    add_to(c, "CurrentHitPoints", hp);
    add_to(c, "MaxHitPoints", hp);
    let fp = (new.force_die - old.force_die) * levels;
    add_to(c, "ForcePoints", fp);
    add_to(c, "CurrentForce", fp);
    add_to(c, "MaxForcePoints", fp);
    if let Some(records) = c.list_mut("LvlStatList") {
        for r in records.iter_mut().filter(|r| r.int("LvlStatClass") == Some(old.id)) {
            r.set_int("LvlStatClass", new.id, Value::Byte(0));
            r.set_int("LvlStatHitDie", new.hit_die, Value::Byte(0));
            r.set_int("LvlStatForce", new.force_die, Value::Byte(0));
            if new.force_die == 0 && r.get("KnownList0").is_some() {
                r.set("KnownList0", Value::List(Vec::new()));
            }
        }
    }
}

/// Removes a class entry when there are two: its levels are taken back first, as if
/// levelled down, then the entry goes with its powers.
pub fn remove_class(c: &mut Struct, index: usize, class: &crate::catalog::Class, xp_for: &dyn Fn(i64) -> Option<i64>) {
    if c.list("ClassList").map_or(true, |l| l.len() < 2 || index >= l.len()) {
        return;
    }
    set_class_level(c, index, 1, class, xp_for);
    add_to(c, "HitPoints", -class.hit_die);
    add_to(c, "CurrentHitPoints", -class.hit_die);
    add_to(c, "MaxHitPoints", -class.hit_die);
    if class.force_die > 0 {
        add_to(c, "ForcePoints", -class.force_die);
        add_to(c, "CurrentForce", -class.force_die);
        add_to(c, "MaxForcePoints", -class.force_die);
    }
    if c.list("LvlStatList").is_some() {
        let pos = c.list("LvlStatList").unwrap().iter().rposition(|r| r.int("LvlStatClass") == Some(class.id));
        if let Some(pos) = pos {
            let record = c.list_mut("LvlStatList").unwrap().remove(pos);
            undo_record(c, &record);
        }
    }
    c.list_mut("ClassList").unwrap().remove(index);
    fit_experience(c, xp_for);
}

// ---- equipment ----

/// The equipment slots, by the struct id the game gives an equipped item (measured in
/// both games' saves), and their names. The second weapon set is KotOR 2's.
pub const SLOTS: [(u32, &str); 11] = [
    (0x1, "Head"),
    (0x2, "Body"),
    (0x8, "Hands"),
    (0x10, "Right weapon"),
    (0x20, "Left weapon"),
    (0x80, "Left arm"),
    (0x100, "Right arm"),
    (0x200, "Implant"),
    (0x400, "Belt"),
    (0x40000, "Right weapon, set 2"),
    (0x80000, "Left weapon, set 2"),
];

pub fn in_slot(c: &Struct, slot: u32) -> Option<&Struct> {
    c.list("Equip_ItemList")?.iter().find(|i| i.id == slot)
}

/// Takes the item out of `slot` with the effects it gave (each names the item's object id
/// as its creator). Returns it without the object id, as the party inventory keeps items.
pub fn unequip(c: &mut Struct, slot: u32) -> Option<Struct> {
    let list = c.list_mut("Equip_ItemList")?;
    let pos = list.iter().position(|i| i.id == slot)?;
    let mut item = list.remove(pos);
    let id = item.int("ObjectId");
    if let (Some(id), Some(effects)) = (id, c.list_mut("EffectList")) {
        effects.retain(|e| e.int("CreatorId") != Some(id));
    }
    item.id = 0;
    item.fields.retain(|(l, _)| l != "ObjectId");
    Some(item)
}

/// Puts `item` into `slot` with a new object id, in slot order.
pub fn equip(c: &mut Struct, slot: u32, mut item: Struct, object_id: u32) {
    if c.list("Equip_ItemList").is_none() {
        c.set("Equip_ItemList", Value::List(Vec::new()));
    }
    item.id = slot;
    item.fields.retain(|(l, _)| l != "ObjectId");
    item.fields.insert(0, ("ObjectId".into(), Value::Dword(object_id)));
    let list = c.list_mut("Equip_ItemList").unwrap();
    list.retain(|i| i.id != slot);
    let at = list.iter().position(|i| i.id > slot).unwrap_or(list.len());
    list.insert(at, item);
}
