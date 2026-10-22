//! The quest database: for each quest, the steps the game takes from its start to each
//! ending, as tools/questdb/build.py drafts them from the game's own scripts and dialogs and
//! a person then checks by playing (data/quests/*.json). Finishing a quest with "as if
//! played" applies every step up to the chosen ending to the save, in order: story
//! switches, items, experience, alignment, credits, and the people and doors of each area
//! the save has been to. Nothing here runs a script; it writes what the script would have.

use crate::formats::gff::{Struct, Value};
use crate::gamedata::GameData;
use crate::games::Game;
use crate::save::{Save, Who};
use serde::Deserialize;

#[derive(Clone, Debug, Deserialize)]
pub struct File {
    pub game: String,
    #[serde(default)]
    pub planet: String,
    #[serde(default)]
    pub checked: bool,
    pub quests: Vec<Quest>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Quest {
    pub tag: String,
    #[serde(default)]
    pub stages: Vec<Stage>,
    #[serde(default)]
    pub notes: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Stage {
    pub stage: i64,
    #[serde(default)]
    pub end: bool,
    #[serde(default)]
    pub steps: Vec<Step>,
}

#[derive(Clone, Debug, Deserialize)]
pub struct Step {
    #[serde(default)]
    pub module: String,
    #[serde(default)]
    pub via: Option<serde_json::Value>,
    #[serde(default)]
    pub needs: Vec<serde_json::Value>,
    #[serde(default)]
    pub does: Vec<serde_json::Value>,
    #[serde(default)]
    pub branch: Option<String>,
}

/// The databases the editor carries, by game.
const FILES: &[(Game, &str)] = include!(concat!(env!("OUT_DIR"), "/quest_files.rs"));

/// The quest's chain, when the database has it.
pub fn quest(game: Game, tag: &str) -> Option<(Quest, bool)> {
    for (g, text) in FILES {
        if *g != game {
            continue;
        }
        let Ok(file) = serde_json::from_str::<File>(text) else { continue };
        if let Some(q) = file.quests.into_iter().find(|q| q.tag.eq_ignore_ascii_case(tag)) {
            return Some((q, file.checked));
        }
    }
    None
}

/// The steps that lead to `ending`: every step of the stages before it (by number) that
/// belongs to no branch, then the ending's own steps. Branched steps of earlier stages are
/// returned apart, for the player to choose.
pub fn path(q: &Quest, ending: i64) -> (Vec<Step>, Vec<Step>) {
    let mut sure = Vec::new();
    let mut choices = Vec::new();
    let mut stages: Vec<&Stage> = q.stages.iter().collect();
    stages.sort_by_key(|s| s.stage);
    for s in stages {
        if s.stage == ending {
            sure.extend(s.steps.iter().cloned());
        } else if s.stage < ending && !s.end {
            for step in &s.steps {
                if step.branch.as_deref().map_or(true, |b| b.trim().is_empty()) {
                    sure.push(step.clone());
                } else {
                    choices.push(step.clone());
                }
            }
        }
    }
    (sure, choices)
}

fn str_of(v: &serde_json::Value) -> String {
    v.as_str().unwrap_or_default().to_string()
}

fn pair(v: &serde_json::Value) -> Option<(String, &serde_json::Value)> {
    let a = v.as_array()?;
    Some((a.first()?.as_str()?.to_string(), a.get(1)?))
}

/// One effect in plain words, for the pop-up.
pub fn describe(effect: &serde_json::Value, data: &GameData) -> String {
    let Some((kind, arg)) = effect.as_object().and_then(|o| o.iter().next()) else { return String::new() };
    let item_name = |resref: &str| -> String {
        data.gff(resref, "uti", crate::formats::erf::RES_TYPE_UTI)
            .and_then(|g| match g.root.get("LocalizedName") {
                Some(Value::LocString(l)) => Some(data.loc(l)),
                _ => None,
            })
            .filter(|n| !n.trim().is_empty())
            .unwrap_or_else(|| resref.to_string())
    };
    match kind.as_str() {
        "set_global_bool" => pair(arg).map(|(n, v)| format!("Story switch {} {}", n, if v.as_bool() == Some(true) { "on" } else { "off" })).unwrap_or_default(),
        "set_global_number" => pair(arg).map(|(n, v)| format!("Story counter {} = {}", n, v)).unwrap_or_default(),
        "give_item" => pair(arg).map(|(r, n)| format!("You get {}{}", item_name(&r), if n.as_i64().unwrap_or(1) > 1 { format!(" x{}", n) } else { String::new() })).unwrap_or_default(),
        "take_item" => pair(arg).map(|(r, _)| format!("{} is taken from you", item_name(&r))).unwrap_or_default(),
        "xp" => format!("+{} XP", arg),
        "light_side" => format!("Light side +{}", arg),
        "dark_side" => format!("Dark side +{}", arg),
        "credits" => format!("{} credits", arg),
        "destroy" => format!("{} leaves the area", str_of(arg)),
        "door_open" => format!("Door {} opens", str_of(arg)),
        "door_unlock" => format!("Door {} unlocks", str_of(arg)),
        "journal" => pair(arg).map(|(t, s)| format!("Journal: {} stage {}", t, s)).unwrap_or_default(),
        "other" => str_of(arg),
        k => k.to_string(),
    }
}

/// Whether the editor can write this effect into a save (cutscenes and the like it cannot).
pub fn can_apply(effect: &serde_json::Value) -> bool {
    effect.as_object().and_then(|o| o.keys().next()).map_or(false, |k| k != "other")
}

/// Applies one step's effects to the save. Returns what could not be applied, in plain
/// words (an area not visited yet: the game builds it fresh from its own files there).
pub fn apply(save: &mut Save, data: &GameData, step: &Step, key: &str) -> Vec<String> {
    let mut skipped = Vec::new();
    for (i, effect) in step.does.iter().enumerate() {
        let Some((kind, arg)) = effect.as_object().and_then(|o| o.iter().next()) else { continue };
        let k = format!("{}.{}", key, i);
        match kind.as_str() {
            "set_global_bool" | "set_global_number" => {
                let Some((name, v)) = pair(arg) else { continue };
                let value = if kind == "set_global_bool" { v.as_bool().map(|b| b as i64) } else { v.as_i64() };
                let Some(value) = value else { continue };
                let mut found = false;
                save.edit_globals(&k, |root| {
                    let all = crate::globals::list(root);
                    if let Some(g) = all.iter().find(|g| g.name.eq_ignore_ascii_case(&name)) {
                        found = true;
                        match g.kind {
                            crate::globals::Kind::Boolean => crate::globals::set_bool(root, g.index, value != 0),
                            crate::globals::Kind::Number => crate::globals::set_number(root, g.index, value),
                            crate::globals::Kind::String => {}
                        }
                    }
                });
                if !found {
                    skipped.push(format!("The save has no story switch {}", name));
                }
            }
            "give_item" => {
                let Some((resref, n)) = pair(arg) else { continue };
                let Some(uti) = data.gff(&resref, "uti", crate::formats::erf::RES_TYPE_UTI) else {
                    skipped.push(format!("Item {} not found in the game", resref));
                    continue;
                };
                let like = save.inventory().first().cloned();
                let count = n.as_i64().unwrap_or(1);
                let item = crate::catalog::item_from_template(&uti.root, like.as_ref(), count);
                // Onto a stack of the same item the party already has, as the game stacks a
                // pick-up, up to baseitems.2da's stacking limit.
                let base = item.int("BaseItem").unwrap_or(0) as usize;
                let limit = data.table("baseitems").int(base, "stacking").unwrap_or(1).max(1);
                let tag = item.string("Tag").unwrap_or_default();
                save.edit_inventory(&k, |items| {
                    if limit > 1 {
                        if let Some(same) = items.iter_mut().find(|it| {
                            it.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(&tag))
                                && it.int("StackSize").unwrap_or(1) + count <= limit
                        }) {
                            let now = same.int("StackSize").unwrap_or(1);
                            same.set_int("StackSize", now + count, Value::Word(1));
                            return;
                        }
                    }
                    items.push(item);
                });
            }
            "take_item" => {
                let Some((resref, _)) = pair(arg) else { continue };
                save.edit_inventory(&k, |items| {
                    if let Some(at) = items.iter().position(|it| {
                        it.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(&resref))
                            || it.string("TemplateResRef").map_or(false, |t| t.eq_ignore_ascii_case(&resref))
                    }) {
                        let stack = items[at].int("StackSize").unwrap_or(1);
                        if stack > 1 {
                            items[at].set_int("StackSize", stack - 1, Value::Word(1));
                        } else {
                            items.remove(at);
                        }
                    }
                });
            }
            "xp" => {
                let n = arg.as_i64().unwrap_or(0);
                save.edit(Who::Player, &k, |c| {
                    let now = crate::creature::experience(c);
                    crate::creature::set_experience(c, now + n);
                });
                let pool = save.party_int("PT_XP_POOL").unwrap_or(0);
                save.set_party_int("PT_XP_POOL", pool + n);
            }
            "light_side" | "dark_side" => {
                let n = arg.as_i64().unwrap_or(0) * if kind == "light_side" { 1 } else { -1 };
                save.edit(Who::Player, &k, |c| {
                    let now = crate::creature::alignment(c);
                    crate::creature::set_alignment(c, (now + n).clamp(0, 100));
                });
            }
            "credits" => {
                let n = arg.as_i64().unwrap_or(0);
                let gold = save.party_int("PT_GOLD").unwrap_or(0);
                save.set_party_int("PT_GOLD", (gold + n).max(0));
            }
            "destroy" | "door_open" | "door_unlock" => {
                let tag = str_of(arg);
                let what = kind.clone();
                let done = save.edit_module_git(&step.module, &k, |git| {
                    let tag_is = |s: &Struct| s.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(&tag));
                    match what.as_str() {
                        "destroy" => {
                            for list in [crate::area::CREATURES, crate::area::PLACEABLES] {
                                if let Some(l) = git.list_mut(list) {
                                    l.retain(|s| !tag_is(s));
                                }
                            }
                        }
                        _ => {
                            if let Some(l) = git.list_mut(crate::area::DOORS) {
                                for d in l.iter_mut().filter(|d| tag_is(d)) {
                                    if what == "door_open" {
                                        d.set_int("OpenState", 1, Value::Byte(0));
                                    }
                                    d.set_int("Locked", 0, Value::Byte(0));
                                }
                            }
                        }
                    }
                });
                if !done {
                    skipped.push(format!("{} happens when you first enter {} (the save has not been there; the game reads the story switches then)", describe(effect, data), step.module));
                }
            }
            "journal" => {
                if let Some((tag, s)) = pair(arg) {
                    let s = s.as_i64().unwrap_or(0);
                    // The game only moves a quest forward.
                    let now = save.quests().into_iter().find(|(t, _)| t.eq_ignore_ascii_case(&tag)).map(|(_, v)| v).unwrap_or(-1);
                    if s > now {
                        save.set_quest(&tag, s);
                    }
                }
            }
            _ => skipped.push(describe(effect, data)),
        }
    }
    skipped
}

// ---- skipping ahead ----
//
// A milestone (data/quests/*-milestone.json, written by tools/questdb/build.py --milestone)
// is the story state every finished run of a chapter ends with: the journal, the story
// switches the rest of the game reads, the items the player holds, the party, and where the
// next chapter begins. Skipping ahead applies it to the save and then sends the player to
// that beginning the way the game's own scripts do (Save::queue_transition).

/// The milestones the editor carries for a game: (chapter, the file).
pub fn milestones(game: Game) -> Vec<(String, serde_json::Value)> {
    let mut out = Vec::new();
    for (g, text) in FILES {
        if *g != game {
            continue;
        }
        let Ok(v) = serde_json::from_str::<serde_json::Value>(text) else { continue };
        if v.get("next_chapter").is_none() {
            continue;
        }
        let planet = v.get("planet").and_then(|p| p.as_str()).unwrap_or_default().to_string();
        out.push((planet, v));
    }
    out
}

/// Applies a milestone to the save and queues the trip to the next chapter. Returns what
/// could not be applied, and the values the data marks as not certain, in plain words.
pub fn skip_to(save: &mut Save, data: &GameData, m: &serde_json::Value) -> Result<Vec<String>, String> {
    let mut does = Vec::new();
    for j in m.get("journal").and_then(|j| j.as_array()).cloned().unwrap_or_default() {
        if let (Some(tag), Some(stage)) = (j.get("tag").and_then(|t| t.as_str()), j.get("stage").and_then(|s| s.as_i64())) {
            does.push(serde_json::json!({ "journal": [tag, stage] }));
        }
    }
    let mut unsure = Vec::new();
    for g in m.get("globals").and_then(|g| g.as_array()).cloned().unwrap_or_default() {
        let Some(name) = g.get("name").and_then(|n| n.as_str()) else { continue };
        let value = g.get("value").cloned().unwrap_or(serde_json::Value::Null);
        if value.is_null() {
            continue;
        }
        if g.get("certain").and_then(|c| c.as_bool()) == Some(false) {
            unsure.push(format!("Story value {} = {} (worked out from the scripts, not seen in play)", name, value));
        }
        let kind = if value.is_boolean() { "set_global_bool" } else { "set_global_number" };
        does.push(serde_json::json!({ kind: [name, value] }));
    }
    let items = m.get("items").and_then(|i| i.get("held_at_end")).and_then(|h| h.as_array()).cloned().unwrap_or_default();
    for it in items {
        let (Some(resref), n) = (it.get("resref").and_then(|r| r.as_str()), it.get("count").and_then(|c| c.as_i64()).unwrap_or(1)) else { continue };
        does.push(serde_json::json!({ "give_item": [resref, n] }));
    }
    // What a full run leaves besides the story (data/quests/*-rewards.json): the enemies'
    // drops and the containers' loot, the containers' class gear by the game's own tests.
    let planet_name = m.get("planet").and_then(|p| p.as_str()).unwrap_or_default().to_string();
    let rewards = rewards(save.game, &planet_name);
    if let Some(r) = rewards.as_ref() {
        for d in r.get("drops").and_then(|d| d.as_array()).cloned().unwrap_or_default() {
            if let (Some(res), n) = (d.get("resref").and_then(|v| v.as_str()), d.get("count").and_then(|v| v.as_i64()).unwrap_or(1)) {
                does.push(serde_json::json!({ "give_item": [res, n] }));
            }
        }
        let player = save.player().cloned();
        for c in r.get("containers").and_then(|c| c.as_array()).cloned().unwrap_or_default() {
            for it in c.get("items").and_then(|i| i.as_array()).cloned().unwrap_or_default() {
                if let (Some(res), n) = (it.get("resref").and_then(|v| v.as_str()), it.get("count").and_then(|v| v.as_i64()).unwrap_or(1)) {
                    does.push(serde_json::json!({ "give_item": [res, n] }));
                }
            }
            for it in c.get("created_by_script").and_then(|i| i.as_array()).cloned().unwrap_or_default() {
                let all: Vec<String> = it.get("when").and_then(|w| serde_json::from_value(w.clone()).ok()).unwrap_or_default();
                let any: Vec<Vec<String>> = it.get("when_any").and_then(|w| serde_json::from_value(w.clone()).ok()).unwrap_or_default();
                let holds = |t: &String| player.as_ref().map_or(false, |p| condition(p, t));
                if all.iter().all(holds) && (any.is_empty() || any.iter().any(|g| g.iter().all(holds))) {
                    if let Some(res) = it.get("resref").and_then(|v| v.as_str()) {
                        does.push(serde_json::json!({ "give_item": [res, 1] }));
                    }
                }
            }
        }
    }
    let step = Step { module: String::new(), via: None, needs: Vec::new(), does, branch: None };
    let planet = m.get("planet").and_then(|p| p.as_str()).unwrap_or("chapter").to_ascii_lowercase();
    let mut notes = apply(save, data, &step, &format!("skip.{}", planet));
    // The XP a full run reaches (kills, plot XP, script XP), for the player and the party
    // pool; never lowered, as the game's SetXP never lowers it.
    if let Some(xp) = rewards.as_ref().and_then(|r| r.get("xp_at_end")).and_then(|v| v.as_i64()) {
        save.edit(Who::Player, &format!("skip.{}.xp", planet), |c| {
            let now = crate::creature::experience(c);
            crate::creature::set_experience(c, now.max(xp));
        });
        let pool = save.party_int("PT_XP_POOL").unwrap_or(0);
        save.set_party_int("PT_XP_POOL", pool.max(xp));
    }
    // The game's own first hop, with its movies: from the Endar Spire that is the vision
    // stage after the escape pod movie, whose script then goes on to Taris by itself, so
    // the story plays as in a real run. Without a chain, straight to the next chapter.
    let next = m.get("next_chapter").ok_or("this milestone has no next chapter")?;
    let hop = next.get("chain").and_then(|c| c.as_array()).and_then(|c| c.first()).unwrap_or(next);
    let module = hop.get("module").and_then(|v| v.as_str()).ok_or("this milestone names no next area")?;
    let waypoint = hop.get("waypoint").and_then(|v| v.as_str()).unwrap_or_default();
    let movies: Vec<&str> = hop.get("movies").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|x| x.as_str()).collect()).unwrap_or_default();
    save.queue_transition(module, waypoint, &movies)?;
    notes.extend(unsure);
    Ok(notes)
}

/// A chapter's rewards file (tools/questdb/rewards.py), when the editor carries one.
pub fn rewards_of(game: Game, planet: &str) -> Option<serde_json::Value> {
    rewards(game, planet)
}

fn rewards(game: Game, planet: &str) -> Option<serde_json::Value> {
    FILES.iter().filter(|(g, _)| *g == game).find_map(|(_, text)| {
        let v = serde_json::from_str::<serde_json::Value>(text).ok()?;
        let same = v.get("planet").and_then(|p| p.as_str()).map_or(false, |p| p.eq_ignore_ascii_case(planet));
        (same && v.get("xp_at_end").is_some()).then_some(v)
    })
}

/// One of the tests the game's scripts make before handing out class gear, against the
/// player: "class is CLASS_TYPE_SOLDIER", "has skill SKILL_STEALTH" (a rank above 0).
fn condition(player: &Struct, test: &str) -> bool {
    const CLASSES: [&str; 6] = ["SOLDIER", "SCOUT", "SCOUNDREL", "JEDIGUARDIAN", "JEDICONSULAR", "JEDISENTINEL"];
    const SKILLS: [&str; 8] = ["COMPUTER_USE", "DEMOLITIONS", "STEALTH", "AWARENESS", "PERSUADE", "REPAIR", "SECURITY", "TREAT_INJURY"];
    if let Some(class) = test.strip_prefix("class is CLASS_TYPE_") {
        let Some(id) = CLASSES.iter().position(|c| *c == class) else { return false };
        return crate::creature::classes(player).iter().any(|(c, _)| *c == id as i64);
    }
    if let Some(skill) = test.strip_prefix("has skill SKILL_") {
        let Some(i) = SKILLS.iter().position(|s| *s == skill) else { return false };
        return crate::creature::skill(player, i) > 0;
    }
    false
}
