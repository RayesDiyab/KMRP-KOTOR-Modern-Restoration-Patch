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
    /// The chapter's own quest (not one another chapter also sets stages of).
    #[serde(default)]
    pub own: bool,
    /// The ending a full run of the chapter reaches (tools/questdb/assemble.py).
    #[serde(default)]
    pub run_ending: Option<i64>,
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
    /// Item templates the game keeps only in an area's own files (KotOR 2 has many), found
    /// there ahead of time for Skip Ahead; looked up after the game's global files.
    #[serde(skip)]
    pub found: std::collections::HashMap<String, crate::formats::gff::Gff>,
}

/// The databases the editor carries, by game.
const FILES: &[(Game, &str)] = include!(concat!(env!("OUT_DIR"), "/quest_files.rs"));

/// The quest's chain, when the database has it.
pub fn quest(game: Game, tag: &str) -> Option<(Quest, bool)> {
    // A quest that runs over several chapters (the Star Forge, the party members' own
    // quests) is in each chapter's file with the stages set there: merged into one chain.
    let mut found: Option<(Quest, bool)> = None;
    for (g, text) in FILES {
        if *g != game {
            continue;
        }
        let Ok(file) = serde_json::from_str::<File>(text) else { continue };
        let Some(q) = file.quests.into_iter().find(|q| q.tag.eq_ignore_ascii_case(tag)) else { continue };
        match found.as_mut() {
            None => found = Some((q, file.checked)),
            Some((have, checked)) => {
                *checked &= file.checked;
                for st in q.stages {
                    match have.stages.iter_mut().find(|x| x.stage == st.stage) {
                        Some(x) => x.steps.extend(st.steps),
                        None => have.stages.push(st),
                    }
                }
                have.stages.sort_by_key(|x| x.stage);
            }
        }
    }
    found
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
        "local" => arg.as_array().map(|a| format!("Local flag {} on {}", a.get(2).cloned().unwrap_or_default(), str_of(a.first().unwrap_or(&serde_json::Value::Null)))).unwrap_or_default(),
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
                let Some(uti) = data.gff(&resref, "uti", crate::formats::erf::RES_TYPE_UTI).or_else(|| step.found.get(&resref.to_ascii_lowercase()).cloned()) else {
                    skipped.push(format!("Item {} not found in the game", resref));
                    continue;
                };
                let count = n.as_i64().unwrap_or(1);
                // Credits (baseitems.2da row 57): picking them up adds their stack size to the
                // party's credits, as the game does; they never stay in the inventory.
                if uti.root.int("BaseItem") == Some(57) {
                    let amount = uti.root.int("StackSize").unwrap_or(1).max(1) * count;
                    let gold = save.party_int("PT_GOLD").unwrap_or(0);
                    save.set_party_int("PT_GOLD", gold + amount);
                    continue;
                }
                let like = save.inventory().first().cloned();
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
            "local" => {
                // A flag the game keeps on an object, the area or the module (its NPCs read
                // theirs to know a talk is done). Objects and the area: in the area's stored
                // copy; the module's own flags are not reachable here.
                let Some(a) = arg.as_array() else { continue };
                let (Some(on), Some(kind), Some(index), Some(value)) = (a.first().and_then(|v| v.as_str()), a.get(1).and_then(|v| v.as_str()), a.get(2).and_then(|v| v.as_u64()), a.get(3).and_then(|v| v.as_i64())) else { continue };
                if on.eq_ignore_ascii_case("module") {
                    continue;
                }
                let (game, number, on) = (save.game, kind == "number", on.to_string());
                let done = save.edit_module_git(&step.module, &k, |git| {
                    if on.eq_ignore_ascii_case("area") {
                        crate::stored::set_local(git, game, number, index as u32, value);
                        return;
                    }
                    for list in [crate::area::CREATURES, crate::area::DOORS, crate::area::PLACEABLES, "TriggerList"] {
                        if let Some(l) = git.list_mut(list) {
                            for o in l.iter_mut().filter(|o| o.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(&on))) {
                                crate::stored::set_local(o, game, number, index as u32, value);
                            }
                        }
                    }
                });
                if !done {
                    skipped.push(format!("{} happens when you first enter {}", describe(effect, data), step.module));
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
    skip_through(save, data, &[m.clone()], None, false)
}

/// Whether the light or the dark side changes anything in these chapters: the story (a
/// chapter's "dark" block), or the credits and alignment a run of each side picks up.
pub fn side_matters(game: Game, chapters: &[serde_json::Value]) -> bool {
    chapters.iter().any(|m| {
        if m.get("dark").is_some() {
            return true;
        }
        let planet = m.get("planet").and_then(|p| p.as_str()).unwrap_or_default();
        rewards(game, planet).and_then(|r| r.get("credits").cloned()).map_or(false, |c| {
            let side = |s: &str| c.get(s).map(|v| (v.get("credits").and_then(|x| x.as_i64()), v.get("light_points").and_then(|x| x.as_i64()), v.get("dark_points").and_then(|x| x.as_i64())));
            side("light") != side("dark")
        })
    })
}

/// The chapter as a run of the chosen side ends it: for the dark side, the milestone with
/// its "dark" block in place of the light-side journal, story values, party and route.
fn for_side(m: &serde_json::Value, dark: bool) -> serde_json::Value {
    let Some(dk) = m.get("dark").filter(|_| dark) else { return m.clone() };
    let mut out = m.clone();
    if let Some(j) = dk.get("journal") {
        out["journal"] = j.clone();
    }
    let overrides = dk.get("globals").and_then(|g| g.as_array()).cloned().unwrap_or_default();
    if let Some(globals) = out.get_mut("globals").and_then(|g| g.as_array_mut()) {
        for o in &overrides {
            let name = o.get("name").and_then(|n| n.as_str()).unwrap_or_default();
            match globals.iter_mut().find(|g| g.get("name").and_then(|n| n.as_str()).map_or(false, |n| n.eq_ignore_ascii_case(name))) {
                Some(g) => {
                    g["value"] = o.get("value").cloned().unwrap_or(serde_json::Value::Null);
                    g["certain"] = o.get("certain").cloned().unwrap_or(serde_json::Value::Bool(false));
                }
                None => globals.push(o.clone()),
            }
        }
    }
    if let Some(party) = dk.get("party") {
        let gone: Vec<i64> = party.get("not_recruited").and_then(|v| serde_json::from_value(v.clone()).ok()).unwrap_or_default();
        let mut recruit: Vec<serde_json::Value> = out["party"]["recruit"].as_array().cloned().unwrap_or_default();
        recruit.retain(|r| !r.get("slot").and_then(|s| s.as_i64()).map_or(false, |s| gone.contains(&s)));
        recruit.extend(party.get("recruit").and_then(|r| r.as_array()).cloned().unwrap_or_default());
        let mut remove: Vec<serde_json::Value> = out["party"]["remove"].as_array().cloned().unwrap_or_default();
        remove.extend(party.get("remove").and_then(|r| r.as_array()).cloned().unwrap_or_default());
        out["party"]["recruit"] = serde_json::Value::Array(recruit);
        out["party"]["remove"] = serde_json::Value::Array(remove);
    }
    if let Some(next) = dk.get("next_chapter").filter(|n| !n.is_null()) {
        out["next_chapter"] = next.clone();
    }
    out
}

/// Skips through several chapters in story order: each one's state applied in turn (so
/// later chapters build on earlier ones, as in play), the XP of the last, every chapter's
/// areas stored as played through, then the last chapter's own route on. `jedi_class` is
/// the choice (0, 1, 2) for a chapter that makes the player a Jedi (Dantooine); `dark` picks
/// the dark side's story, credits and alignment where they differ.
pub fn skip_through(save: &mut Save, data: &GameData, chapters: &[serde_json::Value], jedi_class: Option<usize>, dark: bool) -> Result<Vec<String>, String> {
    skip_through_with(save, data, chapters, jedi_class, dark, None, false)
}

/// KotOR 2's companions who can be trained as Jedi, by what the end of their own conversation
/// chain does (research 2026-10-23): (party slot, the class a_makejedi gives, the player's
/// gender it needs, the story values the chain ends with, a local flag on the companion).
/// Mira's value is 2 on the light side (her dark training sets 4; slot 7 is light-only anyway).
const TRAINABLE: [(usize, i64, Option<bool>, &[(&str, i64)], Option<u32>); 5] = [
    (0, 5, None, &[("000_Atton_ID_Reveal", 6), ("003EBO_Atton_End", 1)], None),
    (1, 3, None, &[], Some(35)), // baodur.dlg E123 / E132 set his local 35 when the offer is made
    (4, 3, Some(false), &[("000_Handmaiden_Jedi", 1), ("000_Kreia_Hand_Mom", 5)], None),
    (7, 5, None, &[("000_Mira_Jedi", 2)], None),
    (11, 4, Some(true), &[("000_Disc_Padawan", 5)], None),
];

/// Trains the companions in the party as Jedi the way the end of each one's conversation
/// chain does (a_makejedi: AddMultiClass), and sets the chain's values to where it ends, so the
/// game does not offer those conversations again. Returns notes.
pub fn train_companions(save: &mut Save, data: &GameData) -> Vec<String> {
    let mut notes = Vec::new();
    if save.game != Game::K2 {
        return notes;
    }
    let female = save.player().map_or(false, |p| p.int("Gender") == Some(1));
    let cat = crate::catalog::Catalog::build(data);
    for (slot, class_id, gender, values, local) in TRAINABLE {
        if gender.map_or(false, |f| f != female) || !save.recruited(slot) {
            continue;
        }
        let Some(class) = cat.class(class_id).cloned() else { continue };
        let already = save.creature(Who::Npc(slot)).map_or(true, |c| crate::creature::classes(c).iter().any(|k| [3, 4, 5].contains(&k.0)));
        if !already {
            save.edit(Who::Npc(slot), &format!("skip.train.{}", slot), |c| {
                crate::creature::add_class(c, &class, None);
                if let Some(bit) = local {
                    crate::stored::set_local(c, Game::K2, false, bit, 1);
                }
            });
            notes.push(format!("Party member {} trained as {}", slot, class.name));
        }
        let does = values.iter().map(|(n, v)| serde_json::json!({ "set_global_number": [n, v] })).collect();
        notes.extend(apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does, branch: None, found: Default::default() }, &format!("skip.train.{}.values", slot)));
    }
    notes
}


/// The prestige classes KotOR 2's Kreia offers (dialog kreia E598 / E590, a_pc_jedi):
/// classes.2da rows by side, in the order Skip Ahead lists them.
pub const PRESTIGE_LIGHT: [i64; 3] = [11, 13, 12]; // Weapon Master, Watchman, Jedi Master
pub const PRESTIGE_DARK: [i64; 3] = [14, 16, 15]; // Marauder, Assassin, Sith Lord

/// Whether Kreia would offer the player a prestige class once the skip is done: KotOR 2, one
/// class so far, a Jedi one, 000_Prestige not 2, level 15 or more at `xp` (c_pc_prestige; the
/// alignment test is the side the player picks).
pub fn prestige_due(save: &Save, data: &GameData, xp: i64) -> bool {
    if save.game != Game::K2 {
        return false;
    }
    let Some(p) = save.player() else { return false };
    let classes = crate::creature::classes(p);
    if classes.len() != 1 || ![3, 4, 5].contains(&classes[0].0) {
        return false;
    }
    let taken = save.globals.as_ref().map(|g| crate::globals::list(&g.root)).unwrap_or_default().iter().any(|g| {
        g.name.eq_ignore_ascii_case("000_Prestige") && g.value == crate::globals::GlobalValue::Number(2)
    });
    let table = data.table("exptable");
    let level = (0..table.rows.len()).filter(|&r| table.int(r, "xp").map_or(false, |need| xp >= need)).count() as i64;
    !taken && level >= 15
}

/// What a chapter's conversations and scripts give a run of one side (credits.py: credits,
/// alignment, influence per party slot), less the conversations whose quests the save had
/// already finished; and the payments the story needs (credits_fixed), less a purchase whose
/// companion the save already had (its "slot").
struct ChapterGains {
    credits: i64,
    net_alignment: i64,
    influence: std::collections::BTreeMap<usize, i64>,
}

fn chapter_gains(c: &serde_json::Value, side: &str, planet: &str, game: Game, before: &Before) -> ChapterGains {
    let quests = dialog_quests(game, planet);
    let done = |dialog: &str| {
        quests.get(&dialog.to_ascii_lowercase()).map_or(false, |qs| {
            !qs.is_empty() && qs.iter().all(|(t, end)| end.map_or(false, |e| before.stage(t) >= e))
        })
    };
    let int = |v: &serde_json::Value, k: &str| v.get(k).and_then(|x| x.as_i64()).unwrap_or(0);
    let total = &c[side];
    let mut g = ChapterGains { credits: int(total, "credits"), net_alignment: int(total, "light_points") - int(total, "dark_points"), influence: Default::default() };
    let mut add_influence = |v: &serde_json::Value, sign: i64| {
        for (slot, x) in v.get("influence").and_then(|v| v.as_object()).cloned().unwrap_or_default() {
            if let (Ok(slot), Some(x)) = (slot.parse::<usize>(), x.as_i64()) {
                *g.influence.entry(slot).or_default() += sign * x;
            }
        }
    };
    add_influence(total, 1);
    for src in c.get("sources").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
        let Some(d) = src.get("dialog").and_then(|v| v.as_str()) else { continue };
        if done(d) {
            let v = &src[side];
            g.credits -= int(v, "credits");
            g.net_alignment -= int(v, "light_points") - int(v, "dark_points");
            add_influence(v, -1);
        }
    }
    for f in c.get("fixed").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
        let bought = f.get("slot").and_then(|v| v.as_u64()).map_or(false, |sl| before.recruited.get(sl as usize).copied().unwrap_or(false));
        if bought {
            g.credits -= int(&f, "credits"); // the total includes it; the save paid it already
        }
    }
    g
}

/// What the save already had before a skip, so nothing a real run gives once is given twice
/// (2026-10-23): the journal, who was in the party, the items held.
struct Before {
    quests: Vec<(String, i64)>,
    recruited: Vec<bool>,
    items: std::collections::HashSet<String>,
}

impl Before {
    fn of(save: &Save) -> Before {
        let mut items = std::collections::HashSet::new();
        for it in save.inventory() {
            for f in ["TemplateResRef", "Tag"] {
                if let Some(v) = it.string(f) {
                    items.insert(v.to_ascii_lowercase());
                }
            }
        }
        Before { quests: save.quests(), recruited: (0..12).map(|i| save.recruited(i)).collect(), items }
    }

    fn stage(&self, tag: &str) -> i64 {
        self.quests.iter().find(|(t, _)| t.eq_ignore_ascii_case(tag)).map_or(-1, |(_, v)| *v)
    }
}

/// Whether the save already met the chapter's Jedi master (KotOR 2, "master_met": a story
/// value, or a flag the master sets on himself in his own conversation): then his count and his
/// teaching are not given again.
fn master_met(save: &Save, m: &serde_json::Value) -> bool {
    let globals = save.globals.as_ref().map(|g| crate::globals::list(&g.root)).unwrap_or_default();
    m.get("master_met").and_then(|v| v.as_array()).cloned().unwrap_or_default().iter().any(|c| {
        if let Some(name) = c.get("global").and_then(|v| v.as_str()) {
            return globals.iter().any(|g| g.name.eq_ignore_ascii_case(name) && match g.value {
                crate::globals::GlobalValue::Number(n) => n > 0,
                crate::globals::GlobalValue::Bool(b) => b,
                _ => false,
            });
        }
        let (Some(module), Some(dialog), Some(bit)) = (c.get("module").and_then(|v| v.as_str()), c.get("dialog").and_then(|v| v.as_str()), c.get("local").and_then(|v| v.as_u64())) else { return false };
        let Some(git) = save.module_git(module) else { return false };
        git.root.list(crate::area::CREATURES).map_or(false, |l| l.iter().any(|o| {
            o.string("Conversation").map_or(false, |d| d.eq_ignore_ascii_case(dialog)) && local_bit(o, bit as u32)
        }))
    })
}

fn local_bit(o: &Struct, bit: u32) -> bool {
    let Some(Value::Struct(t)) = o.get("SWVarTable") else { return false };
    t.list("BitArray").and_then(|l| l.get((bit / 32) as usize)).and_then(|w| w.int("Variable")).map_or(false, |w| (w as u32) & (1 << (bit % 32)) != 0)
}

/// The chapter's own quests each conversation moves on (from the quest file), for the credits
/// a save that already finished those quests has had.
fn dialog_quests(game: Game, planet: &str) -> std::collections::HashMap<String, Vec<(String, Option<i64>)>> {
    let mut out: std::collections::HashMap<String, Vec<(String, Option<i64>)>> = Default::default();
    for (g, text) in FILES {
        if *g != game {
            continue;
        }
        let Ok(file) = serde_json::from_str::<File>(text) else { continue };
        if !file.planet.eq_ignore_ascii_case(planet) {
            continue;
        }
        for q in file.quests.iter().filter(|q| q.own) {
            let end = q.run_ending.or_else(|| q.stages.iter().filter(|s| s.end).map(|s| s.stage).min());
            for st in q.stages.iter().flat_map(|s| s.steps.iter()) {
                if let Some(d) = st.via.as_ref().and_then(|v| v.get("dialog")).and_then(|v| v.as_str()) {
                    let e = out.entry(d.to_ascii_lowercase()).or_default();
                    if !e.iter().any(|(t, _)| t.eq_ignore_ascii_case(&q.tag)) {
                        e.push((q.tag.clone(), end));
                    }
                }
            }
        }
    }
    out
}

/// skip_through, and the prestige class the player picked (a classes.2da row, KotOR 2).
pub fn skip_through_with(save: &mut Save, data: &GameData, chapters: &[serde_json::Value], jedi_class: Option<usize>, dark: bool, prestige: Option<i64>, train: bool) -> Result<Vec<String>, String> {
    let chapters: Vec<serde_json::Value> = chapters.iter().map(|m| for_side(m, dark)).collect();
    let last = chapters.last().cloned().ok_or("no chapter to skip to")?;
    let mut notes = Vec::new();
    let before = Before::of(save);
    let met: Vec<bool> = chapters.iter().map(|m| master_met(save, m)).collect();
    let (mut credits, mut shift) = (0i64, 0i64);
    // KotOR 2: influence won or lost with each companion over the chapters (credits.py).
    let mut influence: std::collections::BTreeMap<usize, i64> = Default::default();
    for (ci, m) in chapters.iter().enumerate() {
        notes.extend(apply_chapter(save, data, m, jedi_class, &before, met[ci]));
        notes.extend(apply_k2_powers(save, data, m, dark, met[ci]));
        // The credits and alignment the chapter's conversations and scripts give a run of
        // this side (tools/questdb/credits.py).
        let planet = m.get("planet").and_then(|p| p.as_str()).unwrap_or_default();
        if let Some(c) = rewards(save.game, planet).and_then(|r| r.get("credits").cloned()) {
            let sname = if dark { "dark" } else { "light" };
            let gains = chapter_gains(&c, sname, planet, save.game, &before);
            credits += gains.credits;
            // A chapter played on one side never moves the player toward the other.
            let net = gains.net_alignment;
            shift += if dark { net.min(0) } else { net.max(0) };
            for (slot, v) in gains.influence {
                *influence.entry(slot).or_default() += v;
            }
        }
    }
    // Influence moves from what the save holds (the game starts a companion at 50 when met),
    // for the companions the party has once the skip is done; 0 to 100.
    for (slot, delta) in influence {
        if !save.recruited(slot) {
            continue;
        }
        let now = save.influence(slot).filter(|v| *v >= 0).unwrap_or(50);
        save.set_influence(slot, now + delta);
    }
    if credits != 0 {
        let gold = save.party_int("PT_GOLD").unwrap_or(0);
        save.set_party_int("PT_GOLD", (gold + credits).max(0));
        notes.push(format!("{} credits from the chapters' quests and conversations ({} side)", credits, if dark { "dark" } else { "light" }));
    }
    if shift != 0 {
        save.edit(Who::Player, "skip.alignment", |c| {
            let now = crate::creature::alignment(c);
            crate::creature::set_alignment(c, (now + shift).clamp(0, 100));
        });
    }
    // The XP a full run reaches by the end of the last chapter (the rewards file's
    // cumulative total), for the player and the party pool; never lowered.
    let planet = last.get("planet").and_then(|p| p.as_str()).unwrap_or_default().to_string();
    if let Some(xp) = rewards(save.game, &planet).and_then(|r| r.get("xp_at_end").and_then(|v| v.as_i64())) {
        save.edit(Who::Player, &format!("skip.{}.xp", planet.to_ascii_lowercase()), |c| {
            let now = crate::creature::experience(c);
            crate::creature::set_experience(c, now.max(xp));
        });
        let pool = save.party_int("PT_XP_POOL").unwrap_or(0);
        save.set_party_int("PT_XP_POOL", pool.max(xp));
    }
    if train {
        notes.extend(train_companions(save, data));
    }
    // KotOR 2's prestige class: what a_pc_jedi does (AddMultiClass), and 000_Prestige 2 as
    // the dialog sets after the choice, when Kreia would have offered it by now.
    if let Some(class_id) = prestige {
        let xp = save.player().map(crate::creature::experience).unwrap_or(0);
        if prestige_due(save, data, xp) {
            let cat = crate::catalog::Catalog::build(data);
            if let Some(class) = cat.class(class_id).cloned() {
                save.edit(Who::Player, "skip.prestige", |c| {
                    crate::creature::add_class(c, &class, None);
                });
                notes.extend(apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does: vec![serde_json::json!({ "set_global_number": ["000_Prestige", 2] })], branch: None, found: Default::default() }, "skip.prestige.global"));
                notes.push(format!("Prestige class {} taken, as Kreia offers it at level 15", class.name));
            }
        }
    }
    // The game's own first hop of the last chapter, with its movies.
    let next = last.get("next_chapter").ok_or("this milestone has no next chapter")?;
    let hop = next.get("chain").and_then(|c| c.as_array()).and_then(|c| c.first()).unwrap_or(next);
    let module = hop.get("module").and_then(|v| v.as_str()).ok_or("this milestone names no next area")?;
    let waypoint = hop.get("waypoint").and_then(|v| v.as_str()).unwrap_or_default();
    let movies: Vec<&str> = hop.get("movies").and_then(|v| v.as_array()).map(|a| a.iter().filter_map(|x| x.as_str()).collect()).unwrap_or_default();
    let mut trip = vec![module.to_ascii_lowercase()];
    if let Some(final_module) = next.get("module").and_then(|v| v.as_str()) {
        trip.push(final_module.to_ascii_lowercase());
    }
    for m in &chapters {
        notes.extend(write_cleared(save, data, m, &trip));
    }
    for m in &chapters {
        notes.extend(close_quests(save, data, m));
    }
    save.queue_transition(module, waypoint, &movies)?;
    notes.dedup();
    Ok(notes)
}

/// KotOR 2: the form a Jedi master teaches in the chapter (a_give_form, read 2026-10-23: the
/// player's classes, G_PC_FORM, the alignment and the forms already known decide; spells.2da
/// rows) and the powers and feats the story grants ("grants", by side).
fn apply_k2_powers(save: &mut Save, data: &GameData, m: &serde_json::Value, dark: bool, met: bool) -> Vec<String> {
    let mut notes = Vec::new();
    let side = if dark { "dark" } else { "light" };
    let force_class = |id: i64| [3, 4, 5, 11, 12, 13, 14, 15, 16].contains(&id);
    let add = |save: &mut Save, spell: Option<i64>, feat: Option<i64>, key: &str| {
        save.edit(Who::Player, key, |c| {
            if let Some(sp) = spell {
                crate::creature::add_power(c, sp, &force_class);
            }
            if let Some(f) = feat {
                crate::creature::add_feat(c, f);
            }
        });
    };
    for g in m.get("grants").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
        if g.get("side").and_then(|v| v.as_str()).map_or(false, |s| s != side) {
            continue;
        }
        let spell = g.get("spell").and_then(|v| v.as_i64());
        let feat = g.get("feat").and_then(|v| v.as_i64());
        add(save, spell, feat, &format!("skip.grant.{:?}.{:?}", spell, feat));
    }
    if m.get("teach_form").and_then(|v| v.as_bool()) != Some(true) || met {
        return notes;
    }
    let Some(p) = save.player().cloned() else { return notes };
    let classes = crate::creature::classes(&p);
    let base = classes.first().map(|c| c.0).unwrap_or(-1);
    let pre = classes.get(1).map(|c| c.0).unwrap_or(255);
    let globals = save.globals.as_ref().map(|g| crate::globals::list(&g.root)).unwrap_or_default();
    let form = globals.iter().find(|g| g.name.eq_ignore_ascii_case("G_PC_FORM")).and_then(|g| match g.value {
        crate::globals::GlobalValue::Number(n) => Some(n),
        _ => None,
    }).unwrap_or(0);
    // the alignment a run of this side has reached (GetGoodEvilValue < 50 is the dark branch)
    let evil = dark;
    let known = crate::creature::powers(&p);
    let acq = |s: i64| known.contains(&s);
    let consular = |f: i64| -> Option<i64> {
        match f {
            0 => Some(if evil { 266 } else { 267 }),
            1 => Some(if evil { if !acq(266) { 266 } else { 267 } } else if !acq(267) { 267 } else { 266 }),
            2 => Some(268),
            _ => None,
        }
    };
    let spell = match (pre, base, form) {
        (255, 3, 0) => Some(261),
        (255, 3, 1) => Some(262),
        (255, 3, 2) => Some(264),
        (255, 5, 0) => Some(262),
        (255, 5, 1) => Some(261),
        (255, 5, 2) => Some(263),
        (255, 4, f) => consular(f),
        (11 | 14, _, 0) => Some(261),
        (11 | 14, _, 1) => Some(if !acq(261) { 261 } else { 262 }),
        (11 | 14, _, 2) => Some(264),
        (13 | 16, _, 0) => Some(262),
        (13 | 16, _, 1) => Some(if !acq(262) { 262 } else { 261 }),
        (13 | 16, _, 2) => Some(263),
        (12 | 15, _, f) => consular(f),
        _ => None,
    };
    let planet = m.get("planet").and_then(|v| v.as_str()).unwrap_or_default().to_ascii_lowercase();
    match spell {
        Some(sp) => {
            add(save, Some(sp), None, &format!("skip.{}.form", planet));
            notes.extend(apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does: vec![serde_json::json!({ "set_global_number": ["G_PC_FORM", form + 1] })], branch: None, found: Default::default() }, &format!("skip.{}.formcount", planet)));
        }
        None => notes.push("No form taught: the player's class or the teaching count is outside the game's table".to_string()),
    }
    notes
}

/// Closes the chapter's own quests the way a full run leaves them, so their NPCs do not offer
/// the talks again whose rewards the skip already gave: the state effects of the route to each
/// quest's ending (the milestone's stage for it, else the run's ending): the journal, story
/// values, the NPCs' own flags, doors, people who leave. Credits, items, XP and alignment are
/// left out (the rewards file counts them). Runs after the areas are stored, so the flags of an
/// area stored as played through land in it too.
fn close_quests(save: &mut Save, data: &GameData, m: &serde_json::Value) -> Vec<String> {
    const STATE: [&str; 7] = ["journal", "set_global_bool", "set_global_number", "local", "destroy", "door_open", "door_unlock"];
    let planet = m.get("planet").and_then(|p| p.as_str()).unwrap_or_default();
    let milestone_stage = |tag: &str| {
        m.get("journal").and_then(|j| j.as_array()).and_then(|j| {
            j.iter().find(|e| e.get("tag").and_then(|t| t.as_str()).map_or(false, |t| t.eq_ignore_ascii_case(tag))).and_then(|e| e.get("stage").and_then(|s| s.as_i64()))
        })
    };
    let mut closed = 0;
    let mut later = 0;
    for (g, text) in FILES {
        if *g != save.game {
            continue;
        }
        let Ok(file) = serde_json::from_str::<File>(text) else { continue };
        if !file.planet.eq_ignore_ascii_case(planet) {
            continue;
        }
        for q in file.quests.iter().filter(|q| q.own) {
            let Some(ending) = milestone_stage(&q.tag).or(q.run_ending) else { continue };
            let (steps, _choices) = path(q, ending);
            for (i, st) in steps.iter().enumerate() {
                let does: Vec<serde_json::Value> = st.does.iter().filter(|e| e.as_object().and_then(|o| o.keys().next()).map_or(false, |k| STATE.contains(&k.as_str()))).cloned().collect();
                if does.is_empty() {
                    continue;
                }
                let step = Step { module: st.module.clone(), via: None, needs: Vec::new(), does, branch: None, found: Default::default() };
                later += apply(save, data, &step, &format!("skip.close.{}.{}", q.tag.to_ascii_lowercase(), i)).len();
            }
            let now = save.quests().into_iter().find(|(t, _)| t.eq_ignore_ascii_case(&q.tag)).map(|(_, v)| v).unwrap_or(-1);
            if ending > now {
                save.set_quest(&q.tag, ending);
            }
            closed += 1;
        }
    }
    let mut notes = Vec::new();
    if closed > 0 {
        notes.push(format!("{}: {} quests closed as a full run ends them, so their people do not offer them again{}", planet, closed,
            if later > 0 { format!(" ({} of their changes wait in areas the save has not been to; the game sets those itself there)", later) } else { String::new() }));
    }
    notes
}

/// One chapter's end state: the journal (and the quests the game itself removes), the story
/// values, the star map count, the items, the loot, the party, the Jedi class.
fn apply_chapter(save: &mut Save, data: &GameData, m: &serde_json::Value, jedi_class: Option<usize>, before: &Before, met: bool) -> Vec<String> {
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
        if before.items.contains(&resref.to_ascii_lowercase()) {
            continue; // the story gave it already
        }
        does.push(serde_json::json!({ "give_item": [resref, n] }));
    }
    // The chapter's areas the save has been to, as it holds them, and as the game ships them:
    // a container already emptied there, or every enemy of a kind already dead, gave its loot.
    let visited: Vec<(String, Struct)> = cleared_of(m).into_iter().filter_map(|(module, _, _)| save.module_git(&module).map(|g| (module, g.root))).collect();
    let templates = |git: &Struct| -> std::collections::HashMap<String, i64> {
        let mut out = std::collections::HashMap::new();
        for c in git.list(crate::area::CREATURES).cloned().unwrap_or_default() {
            if let Some(t) = c.string("TemplateResRef") {
                *out.entry(t.to_ascii_lowercase()).or_insert(0) += 1;
            }
        }
        out
    };
    let mut dead: std::collections::HashMap<String, (i64, i64)> = Default::default(); // template: (shipped in visited, alive)
    for (module, git) in &visited {
        let now = templates(git);
        if let Some(shipped) = crate::map::game_git(data, module) {
            for (t, n) in templates(&shipped.root) {
                let e = dead.entry(t.clone()).or_insert((0, 0));
                e.0 += n;
                e.1 += now.get(&t).copied().unwrap_or(0);
            }
        }
    }
    let all_killed = |from: &[String]| !from.is_empty() && from.iter().all(|t| dead.get(&t.to_ascii_lowercase()).map_or(false, |(n, alive)| *n > 0 && *alive == 0));
    let looted = |module: &str, tag: &str| {
        visited.iter().find(|(m, _)| m.eq_ignore_ascii_case(module)).map_or(false, |(_, git)| {
            git.list(crate::area::PLACEABLES).map_or(false, |l| l.iter().any(|p| {
                p.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(tag)) && p.list("ItemList").map_or(true, |i| i.is_empty())
            }))
        })
    };
    // What a full run leaves besides the story: the enemies' drops and the containers' loot,
    // the containers' class gear by the game's own tests.
    let planet_name = m.get("planet").and_then(|p| p.as_str()).unwrap_or_default().to_string();
    if let Some(r) = rewards(save.game, &planet_name) {
        for d in r.get("drops").and_then(|d| d.as_array()).cloned().unwrap_or_default() {
            let from: Vec<String> = d.get("from").and_then(|v| serde_json::from_value(v.clone()).ok()).unwrap_or_default();
            if all_killed(&from) {
                continue; // the player killed them and took this already
            }
            if let (Some(res), n) = (d.get("resref").and_then(|v| v.as_str()), d.get("count").and_then(|v| v.as_i64()).unwrap_or(1)) {
                does.push(serde_json::json!({ "give_item": [res, n] }));
            }
        }
        let player = save.player().cloned();
        for c in r.get("containers").and_then(|c| c.as_array()).cloned().unwrap_or_default() {
            let (cm, ct) = (c.get("module").and_then(|v| v.as_str()).unwrap_or_default(), c.get("container").and_then(|v| v.as_str()).unwrap_or_default());
            if !ct.is_empty() && looted(cm, ct) {
                continue; // emptied in the save already
            }
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
    let planet = planet_name.to_ascii_lowercase();
    let found = area_items(data, m, &does);
    let mut notes = apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does, branch: None, found }, &format!("skip.{}", planet));

    // The quests the game itself takes out of the journal at the chapter's end.
    for tag in m.get("journal_remove").and_then(|j| j.as_array()).cloned().unwrap_or_default() {
        if let Some(tag) = tag.as_str() {
            save.remove_quest(tag);
        }
    }

    // A number several chapters raise, each by its own amount (KotOR 2's masters found,
    // 000_Jedi_Found): added to what the save holds, once per chapter skipped.
    for inc in m.get("increments").and_then(|v| v.as_array()).cloned().unwrap_or_default().into_iter().filter(|_| !met) {
        let (Some(name), Some(add)) = (inc.get("name").and_then(|v| v.as_str()), inc.get("add").and_then(|v| v.as_i64())) else { continue };
        let now = save.globals.as_ref().map(|g| crate::globals::list(&g.root)).unwrap_or_default().iter().find(|g| g.name.eq_ignore_ascii_case(name)).and_then(|g| match g.value {
            crate::globals::GlobalValue::Number(n) => Some(n),
            _ => None,
        });
        let value = now.unwrap_or(0) + add;
        notes.extend(apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does: vec![serde_json::json!({ "set_global_number": [name, value] })], branch: None, found: Default::default() }, &format!("skip.{}.inc", planet)));
    }

    // The star maps, counted the game's way: the counter is the base and so much per planet
    // whose map is found, and reaching a count sets what the game's own script sets then
    // (the Leviathan capture after the third planet, the Unknown World after the fourth).
    if let Some(sm) = m.get("star_map").filter(|v| !v.is_null()) {
        let flags: Vec<String> = sm.get("planet_flags").and_then(|f| serde_json::from_value(f.clone()).ok()).unwrap_or_default();
        let found = save
            .globals
            .as_ref()
            .map(|g| crate::globals::list(&g.root))
            .unwrap_or_default()
            .iter()
            .filter(|g| flags.iter().any(|f| f.eq_ignore_ascii_case(&g.name)) && g.value == crate::globals::GlobalValue::Bool(true))
            .count() as i64;
        let count = sm.get("base").and_then(|v| v.as_i64()).unwrap_or(10) + sm.get("per_planet").and_then(|v| v.as_i64()).unwrap_or(10) * found;
        let mut does = Vec::new();
        if let Some(counter) = sm.get("counter").and_then(|v| v.as_str()) {
            does.push(serde_json::json!({ "set_global_number": [counter, count] }));
        }
        for on in sm.get("on_count").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
            if on.get("count").and_then(|v| v.as_i64()) != Some(count) {
                continue;
            }
            let now = save.globals.as_ref().map(|g| crate::globals::list(&g.root)).unwrap_or_default();
            for st in on.get("set").and_then(|v| v.as_array()).cloned().unwrap_or_default() {
                let (Some(name), Some(value)) = (st.get("name").and_then(|v| v.as_str()), st.get("value").and_then(|v| v.as_i64())) else { continue };
                if let Some(below) = st.get("only_if_below").and_then(|v| v.as_i64()) {
                    let cur = now.iter().find(|g| g.name.eq_ignore_ascii_case(name)).and_then(|g| match g.value {
                        crate::globals::GlobalValue::Number(n) => Some(n),
                        _ => None,
                    });
                    if cur.map_or(false, |c| c >= below) {
                        continue;
                    }
                }
                does.push(serde_json::json!({ "set_global_number": [name, value] }));
            }
            if let Some(j) = on.get("journal").and_then(|v| v.as_array()) {
                if let (Some(tag), Some(stage)) = (j.first().and_then(|v| v.as_str()), j.get(1).and_then(|v| v.as_i64())) {
                    does.push(serde_json::json!({ "journal": [tag, stage] }));
                }
            }
        }
        notes.extend(apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does, branch: None, found: Default::default() }, &format!("skip.{}.starmap", planet)));
    }

    // Companions: who joins (AddAvailableNPCByTemplate) and who leaves.
    let party = m.get("party").cloned().unwrap_or_default();
    // KotOR 2's Handmaiden joins a male player and the Disciple a female one ("when").
    let female = save.player().map_or(false, |p| p.int("Gender") == Some(1));
    for r in party.get("recruit").and_then(|r| r.as_array()).cloned().unwrap_or_default() {
        let (Some(slot), Some(template)) = (r.get("slot").and_then(|v| v.as_i64()), r.get("template").and_then(|v| v.as_str())) else { continue };
        match r.get("when").and_then(|w| w.as_str()) {
            Some("male") if female => continue,
            Some("female") if !female => continue,
            _ => {}
        }
        // A template some chapters keep in the recruiting area's own files (the dark side's
        // p_bastilla004 is only in unk_m44ac): the area's copy first, as the game loads it there.
        let module = r.get("module").and_then(|v| v.as_str()).unwrap_or_default();
        let from_module = (!module.is_empty())
            .then(|| crate::map::ModuleFiles::open(&data.root, module))
            .and_then(|f| f.read(template, crate::formats::erf::RES_TYPE_UTC))
            .and_then(|d| crate::formats::gff::Gff::read(&d).ok());
        match from_module.or_else(|| data.gff(template, "utc", crate::formats::erf::RES_TYPE_UTC)) {
            Some(utc) => {
                if let Err(e) = save.recruit_from_template(slot.max(0) as usize, &utc.root) {
                    notes.push(format!("Party member {} not recruited: {}", template, e));
                }
            }
            None => notes.push(format!("Party member template {} not found in the game", template)),
        }
    }
    for r in party.get("remove").and_then(|r| r.as_array()).cloned().unwrap_or_default() {
        if let Some(slot) = r.as_i64().or_else(|| r.get("slot").and_then(|v| v.as_i64())) {
            save.set_recruited(slot.max(0) as usize, false);
        }
    }

    // Becoming a Jedi: the class the player picks, a level of it, its lightsaber, and the
    // story value the game sets for that path.
    if let (Some(jc), Some(pick)) = (m.get("jedi_class"), jedi_class) {
        if let Some(choice) = jc.get("choices").and_then(|c| c.as_array()).and_then(|c| c.get(pick)).cloned() {
            let variable = jc.get("variable").and_then(|v| v.as_str()).unwrap_or("DAN_PATH_STATE");
            let mut does = Vec::new();
            if let Some(ps) = choice.get("path_state").and_then(|v| v.as_i64()) {
                does.push(serde_json::json!({ "set_global_number": [variable, ps] }));
            }
            if let Some(saber) = choice.get("lightsaber").and_then(|v| v.as_str()).filter(|s| !before.items.contains(&s.to_ascii_lowercase())) {
                does.push(serde_json::json!({ "give_item": [saber, 1] }));
            }
            notes.extend(apply(save, data, &Step { module: String::new(), via: None, needs: Vec::new(), does, branch: None, found: Default::default() }, &format!("skip.{}.jedi", planet)));
            if let Some(class_id) = choice.get("class").and_then(|v| v.as_i64()) {
                let cat = crate::catalog::Catalog::build(data);
                if let Some(class) = cat.class(class_id).cloned() {
                    save.edit(Who::Player, &format!("skip.{}.class", planet), |c| {
                        crate::creature::add_class(c, &class, None);
                    });
                }
            }
        }
    }
    notes.extend(unsure);
    notes
}

/// The items of `does` the game's global files lack, from the chapter's own areas (the
/// milestone's "cleared" modules): KotOR 2 keeps many loot and quest items only there.
fn area_items(data: &GameData, m: &serde_json::Value, does: &[serde_json::Value]) -> std::collections::HashMap<String, crate::formats::gff::Gff> {
    let mut want: Vec<String> = does
        .iter()
        .filter_map(|e| e.get("give_item").and_then(|g| g.get(0)).and_then(|r| r.as_str()))
        .map(|r| r.to_ascii_lowercase())
        .filter(|r| data.gff(r, "uti", crate::formats::erf::RES_TYPE_UTI).is_none())
        .collect();
    want.sort();
    want.dedup();
    let mut out = std::collections::HashMap::new();
    if want.is_empty() {
        return out;
    }
    let modules: Vec<String> = m.get("cleared").and_then(|c| c.as_array()).map(|c| c.iter().filter_map(|x| x.get("module").and_then(|v| v.as_str()).map(|s| s.to_string())).collect()).unwrap_or_default();
    for module in modules {
        let files = crate::map::ModuleFiles::open(&data.root, &module);
        for r in &want {
            if out.contains_key(r) {
                continue;
            }
            if let Some(g) = files.read(r, crate::formats::erf::RES_TYPE_UTI).and_then(|d| crate::formats::gff::Gff::read(&d).ok()) {
                out.insert(r.clone(), g);
            }
        }
        if out.len() == want.len() {
            break;
        }
    }
    out
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

/// The chapter's per-area "played through" data (the milestone's "cleared"), read leniently:
/// a map or a list of modules, each with remove, doors, containers_looted, locals and
/// can_return. Tags may be plain strings or objects with a "tag".
fn cleared_of(m: &serde_json::Value) -> Vec<(String, crate::stored::Cleared, bool)> {
    let list = m.get("cleared").and_then(|c| c.as_array()).cloned().unwrap_or_default();
    let tags = |v: Option<&serde_json::Value>| -> Vec<String> {
        v.and_then(|x| x.as_array())
            .map(|a| a.iter().filter_map(|e| e.as_str().map(|s| s.to_string()).or_else(|| e.get("tag").and_then(|t| t.as_str()).map(|s| s.to_string()))).collect())
            .unwrap_or_default()
    };
    list.into_iter()
        .filter_map(|v| {
            let module = v.get("module").and_then(|x| x.as_str())?.to_ascii_lowercase();
            let mut c = crate::stored::Cleared::default();
            c.remove = tags(v.get("remove"));
            c.remove.extend(tags(v.get("spawned_and_killed")));
            for d in v.get("doors").and_then(|d| d.as_array()).cloned().unwrap_or_default() {
                let Some(tag) = d.get("tag").and_then(|t| t.as_str()) else { continue };
                if d.get("open").and_then(|x| x.as_bool()).unwrap_or(false) {
                    c.open.push(tag.to_string());
                }
                if d.get("unlocked").and_then(|x| x.as_bool()).unwrap_or(false) {
                    c.unlock.push(tag.to_string());
                }
            }
            c.looted = tags(v.get("containers_looted"));
            // Locals with a known value: booleans that end TRUE, numbers with their value.
            for l in v.get("locals").and_then(|x| x.as_array()).cloned().unwrap_or_default() {
                let Some(index) = l.get("index").and_then(|x| x.as_u64()).map(|x| x as u32) else { continue };
                let object = l.get("object").and_then(|x| x.as_str()).unwrap_or_default();
                let tag = l.get("tag").and_then(|x| x.as_str()).unwrap_or_default().to_string();
                let value = l.get("value").cloned().unwrap_or_default();
                let number = match &value {
                    serde_json::Value::Bool(true) => None,
                    serde_json::Value::Number(n) => n.as_i64(),
                    _ => continue,
                };
                match (object, number) {
                    ("area", None) => c.area_bits.push(index),
                    ("module", None) => c.module_bits.push(index),
                    ("area", Some(n)) => c.area_numbers.push((index, n)),
                    ("module", Some(n)) => c.module_numbers.push((index, n)),
                    (_, None) if !tag.is_empty() => c.object_bits.push((tag, index)),
                    (_, Some(n)) if !tag.is_empty() => c.object_numbers.push((tag, index, n)),
                    _ => {}
                }
            }
            let can_return = v.get("returnable").or_else(|| v.get("can_return")).and_then(|x| x.as_bool()).unwrap_or(false);
            Some((module, c, can_return))
        })
        .collect()
}

/// Brings a stored area the player has been to to the state a full run leaves it in.
fn reconcile_visited(save: &mut Save, module: &str, c: &crate::stored::Cleared) {
    let game = save.game;
    let c = c.clone();
    save.edit_module_git(module, &format!("skip.visited.{}", module), |git| {
        let tag_in = |o: &Struct, list: &[String]| o.string("Tag").map_or(false, |t| list.iter().any(|x| x.eq_ignore_ascii_case(&t)));
        if let Some(l) = git.list_mut(crate::area::CREATURES) {
            l.retain(|o| !tag_in(o, &c.remove));
        }
        if let Some(l) = git.list_mut(crate::area::DOORS) {
            for d in l.iter_mut() {
                if tag_in(d, &c.open) {
                    d.set_int("OpenState", 1, Value::Byte(0));
                }
                if tag_in(d, &c.open) || tag_in(d, &c.unlock) {
                    d.set_int("Locked", 0, Value::Byte(0));
                }
            }
        }
        if let Some(l) = git.list_mut(crate::area::PLACEABLES) {
            for p in l.iter_mut().filter(|p| tag_in(p, &c.looted)) {
                if p.get("ItemList").is_some() {
                    p.set("ItemList", Value::List(Vec::new()));
                }
            }
        }
        for &b in &c.area_bits {
            crate::stored::set_local(git, game, false, b, 1);
        }
        for &(i, n) in &c.area_numbers {
            crate::stored::set_local(git, game, true, i, n);
        }
        for list in [crate::area::CREATURES, crate::area::DOORS, crate::area::PLACEABLES, "TriggerList"] {
            if let Some(l) = git.list_mut(list) {
                for o in l.iter_mut() {
                    let Some(t) = o.string("Tag") else { continue };
                    for (tag, b) in c.object_bits.iter().chain(c.trigger_bits.iter()) {
                        if tag.eq_ignore_ascii_case(&t) {
                            crate::stored::set_local(o, game, false, *b, 1);
                        }
                    }
                    for (tag, i, n) in &c.object_numbers {
                        if tag.eq_ignore_ascii_case(&t) {
                            crate::stored::set_local(o, game, true, *i, *n);
                        }
                    }
                }
            }
        }
    });
}

/// Writes the played-through stored copies of the chapter's areas the player can come back
/// to, never over an area the save has been to, and only for save groups the trip on keeps
/// (modulesave.2da: entering a module deletes its deletesavegrouponenter group, so a copy of
/// that group would be thrown away). Returns notes.
fn write_cleared(save: &mut Save, data: &GameData, m: &serde_json::Value, trip: &[String]) -> Vec<String> {
    let table = data.table("modulesave");
    let row_of = |module: &str| (0..table.rows.len()).find(|&r| table.cell(r, "modulename").map_or(false, |n| n.eq_ignore_ascii_case(module)));
    let deleted: Vec<i64> = trip.iter().filter_map(|t| row_of(t).and_then(|r| table.int(r, "deletesavegrouponenter"))).collect();
    let Some((last_ifo, base)) = save.current_module_parts() else { return Vec::new() };
    let mut notes = Vec::new();
    let mut written = 0;
    for (module, cleared, can_return) in cleared_of(m) {
        if save.module_git(&module).is_some() {
            // An area the player has been to keeps its stored state; brought to how a full run
            // leaves it: the one-time enemies still there gone, doors opened, the looted
            // containers emptied (their loot is in the skip's), the flags set.
            reconcile_visited(save, &module, &cleared);
            continue;
        }
        if !can_return {
            continue;
        }
        let Some(r) = row_of(&module) else { continue };
        if table.int(r, "includeinsave") != Some(1) || table.int(r, "savegroup").map_or(true, |g| deleted.contains(&g)) {
            continue;
        }
        match crate::stored::played_through(data, &module, &cleared, &last_ifo, &base) {
            Some(bytes) => {
                if save.add_stored_module(&module, bytes) {
                    written += 1;
                }
            }
            None => notes.push(format!("The area {} could not be prepared as played (its game files were not found)", module)),
        }
    }
    if written > 0 {
        notes.push(format!("{} areas of the chapter are stored as played through: come back and its one-time enemies are gone, its doors open, its containers looted", written));
    }
    notes
}
