//! Changes made to copies of every save on this machine (in the system's temporary
//! folder; the real saves are only read), written, read back and checked: each change is
//! there, nothing else moved, and every file is still well formed. Covers the bugs other
//! editors had: removing one Force power removes only that one, a new class brings its
//! level record, Health edits go to the stored base.

use kse_core::catalog::{self, Catalog};
use kse_core::creature;
use kse_core::formats::erf::RES_TYPE_UTI;
use kse_core::formats::gff::Value;
use kse_core::gamedata::GameData;
use kse_core::games::{find_installs, find_saves, Game};
use kse_core::globals::{self, GlobalValue};
use kse_core::save::{Save, Who};
use std::fs;
use std::path::{Path, PathBuf};

fn copy_dir(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for e in fs::read_dir(from).unwrap().filter_map(|e| e.ok()) {
        if e.path().is_file() {
            fs::copy(e.path(), to.join(e.file_name())).unwrap();
        }
    }
}

fn scratch(name: &str) -> PathBuf {
    let dir = std::env::temp_dir().join("kmrp-save-editor-tests").join(name);
    let _ = fs::remove_dir_all(&dir);
    dir
}

#[test]
fn edits_survive_a_write() {
    let installs = find_installs(&[]);
    let mut checked = 0;
    for game in [Game::K1, Game::K2] {
        let Some(install) = installs.iter().find(|i| i.game == game) else { continue };
        let data = GameData::open(game, &install.path);
        let cat = Catalog::build(&data);
        let templates = catalog::item_templates(&data);
        assert!(!templates.is_empty(), "{:?}: no item templates", game);
        for folder in find_saves(&installs, game, &[]) {
            let name = folder.path.file_name().unwrap().to_string_lossy().to_string();
            let work = scratch(&format!("{:?}-{}", game, name));
            copy_dir(&folder.path, &work);
            let backups = scratch(&format!("{:?}-{}-backups", game, name));
            let mut save = Save::open(&work).unwrap();
            let before = Save::open(&work).unwrap();

            // The player: attributes, skills, XP, alignment, a feat, a power.
            save.edit(Who::Player, "Str", |c| creature::set_attribute(c, "Str", 17));
            save.edit(Who::Player, "skill7", |c| creature::set_skill(c, 7, 9));
            save.edit(Who::Player, "xp", |c| creature::set_experience(c, 12345));
            save.edit(Who::Player, "align", |c| creature::set_alignment(c, 77));
            let feat = cat.feats.iter().find(|f| !creature::feats(save.player().unwrap()).contains(&f.id)).unwrap().id;
            save.edit(Who::Player, "feat", |c| {
                creature::add_feat(c, feat);
            });
            let powers_before = creature::powers(save.player().unwrap());
            let had_powers = powers_before.len();
            if had_powers >= 2 {
                let gone = powers_before[0];
                save.edit(Who::Player, "power", |c| {
                    creature::remove_power(c, gone);
                });
            }
            // Party: credits, an item, influence, a global.
            save.set_party_int("PT_GOLD", 424242);
            let like = save.inventory().first().cloned();
            let t = &templates[templates.len() / 2];
            let uti = data.gff(&t.resref, "uti", RES_TYPE_UTI).unwrap();
            let item = catalog::item_from_template(&uti.root, like.as_ref(), 1);
            let items_before = save.inventory().len();
            save.edit_inventory("add", |items| items.push(item.clone()));
            if game == Game::K2 {
                save.set_influence(0, 63);
            }
            let first_bool = save.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default().into_iter().find(|g| g.kind == globals::Kind::Boolean);
            if let Some(g) = first_bool.clone() {
                let flipped = GlobalValue::Bool(g.value != GlobalValue::Bool(true));
                save.edit_globals("b", |root| globals::set(root, &g, &flipped));
            }
            // An NPC, in every copy the save has of them.
            let npc = save.npcs().first().copied();
            if let Some(n) = npc {
                save.edit(Who::Npc(n), "Con", |c| creature::set_attribute(c, "Con", 19));
            }

            save.write(&backups).unwrap();
            let after = Save::open(&work).unwrap();
            let p = after.player().unwrap();
            assert_eq!(creature::attribute(p, "Str"), 17, "{}", name);
            assert_eq!(creature::skill(p, 7), 9, "{}", name);
            assert_eq!(creature::experience(p), 12345, "{}", name);
            assert_eq!(creature::alignment(p), 77, "{}", name);
            assert!(creature::feats(p).contains(&feat), "{}", name);
            if had_powers >= 2 {
                assert_eq!(creature::powers(p).len(), had_powers - 1, "{}: one power removed, not all", name);
            }
            assert_eq!(after.party_int("PT_GOLD"), Some(424242), "{}", name);
            assert_eq!(after.inventory().len(), items_before + 1, "{}", name);
            if game == Game::K2 {
                assert_eq!(after.influence(0), Some(63), "{}", name);
            }
            if let Some(g) = first_bool {
                let now = globals::list(&after.globals.as_ref().unwrap().root);
                assert_ne!(now[g.index].value, g.value, "{}", name);
            }
            if let Some(n) = npc {
                assert_eq!(creature::attribute(after.creature(Who::Npc(n)).unwrap(), "Con"), 19, "{}", name);
            }
            // Nothing else moved: the other attributes and the time played.
            assert_eq!(creature::attribute(p, "Dex"), creature::attribute(before.player().unwrap(), "Dex"));
            assert_eq!(after.party_int("PT_PLAYEDSECONDS"), before.party_int("PT_PLAYEDSECONDS"));
            // The backup is the save as it was.
            let backup = fs::read_dir(backups.join(work.file_name().unwrap())).unwrap().next().unwrap().unwrap().path();
            let old = Save::open(&backup).unwrap();
            assert_eq!(creature::attribute(old.player().unwrap(), "Str"), creature::attribute(before.player().unwrap(), "Str"));
            println!("{:?} {}: every change read back", game, name);
            checked += 1;
        }
    }
    println!("{} saves edited", checked);
}

#[test]
fn a_new_class_brings_its_level_record() {
    let installs = find_installs(&[]);
    let Some(install) = installs.iter().find(|i| i.game == Game::K1) else { return };
    let data = GameData::open(Game::K1, &install.path);
    let cat = Catalog::build(&data);
    for folder in find_saves(&installs, Game::K1, &[]) {
        let save = Save::open(&folder.path).unwrap();
        let mut pc = save.player().unwrap().clone();
        if creature::classes(&pc).len() != 1 {
            continue;
        }
        let levels = pc.list("LvlStatList").map_or(0, |l| l.len());
        let hp = pc.int("HitPoints").unwrap();
        let class = cat.classes.iter().find(|c| c.force_die > 0 && !creature::classes(&pc).iter().any(|(id, _)| *id == c.id)).unwrap().clone();
        let need = cat.xp_for(creature::level(&pc) + 1);
        assert!(creature::add_class(&mut pc, &class, need));
        assert_eq!(creature::classes(&pc).len(), 2);
        assert_eq!(pc.list("LvlStatList").map_or(0, |l| l.len()), levels + 1, "one level record per level");
        assert_eq!(pc.int("HitPoints").unwrap(), hp + class.hit_die);
        let entry = &pc.list("ClassList").unwrap()[1];
        assert!(entry.list("KnownList0").is_some(), "a Jedi class can hold powers");
        assert!(matches!(entry.get("ClassLevel"), Some(Value::Short(1))));
        return;
    }
}

#[test]
fn kse_features_survive_a_write() {
    let installs = find_installs(&[]);
    for game in [Game::K1, Game::K2] {
        let Some(install) = installs.iter().find(|i| i.game == game) else { continue };
        let data = GameData::open(game, &install.path);
        let cat = Catalog::build(&data);
        for folder in find_saves(&installs, game, &[]) {
            let name = folder.path.file_name().unwrap().to_string_lossy().to_string();
            let work = scratch(&format!("kse-{:?}-{}", game, name));
            copy_dir(&folder.path, &work);
            let backups = scratch(&format!("kse-{:?}-{}-backups", game, name));
            let mut save = Save::open(&work).unwrap();
            let p = save.player().unwrap().clone();
            // Body armour off and on again: the same item, a new object id.
            let body = creature::in_slot(&p, 0x2).and_then(|i| i.string("Tag"));
            let items = save.inventory().len();
            if body.is_some() {
                assert!(save.unequip(Who::Player, 0x2));
                assert_eq!(save.inventory().len(), items + 1);
                assert!(save.equip(Who::Player, 0x2, items));
                assert_eq!(save.inventory().len(), items);
            }
            // A level down and up again in the last class.
            let classes = creature::classes(&p);
            let index = classes.len() - 1;
            let (id, lv) = classes[index];
            let class = cat.class(id).unwrap().clone();
            let xp = |l: i64| cat.xp_for(l);
            if lv > 1 {
                save.edit(Who::Player, "down", |c| creature::set_class_level(c, index, lv - 1, &class, &xp));
                save.edit(Who::Player, "up", |c| creature::set_class_level(c, index, lv, &class, &xp));
            }
            // The party and a quest.
            let members: Vec<usize> = save.npcs().into_iter().filter(|n| save.recruited(*n)).take(2).collect();
            save.set_party_members(&members).unwrap();
            save.set_quest("kmrp_test_quest", 10);
            save.write(&backups).unwrap();

            let after = Save::open(&work).unwrap();
            let q = after.player().unwrap();
            assert_eq!(creature::in_slot(q, 0x2).and_then(|i| i.string("Tag")), body, "{}", name);
            assert_eq!(creature::classes(q)[index].1, lv, "{}", name);
            // As many level records as before (a save edited by another tool may not have
            // one per level to begin with; Game22 here has 41 for 40 levels).
            assert_eq!(
                q.list("LvlStatList").map(|l| l.len()),
                p.list("LvlStatList").map(|l| l.len()),
                "{}: level records",
                name
            );
            assert_eq!(after.party_members(), members, "{}", name);
            assert!(after.quests().contains(&("kmrp_test_quest".to_string(), 10)), "{}", name);
        }
    }
}

/// Spawning: a creature from a game template and a copy of one already in the area go into
/// copies of every save; written and read back, both are there with ids nothing else uses,
/// the template one with its spawn script still to run, and Module.ifo's counter past them.
#[test]
fn spawned_creatures_survive_a_write() {
    use kse_core::area;
    use kse_core::formats::erf::RES_TYPE_UTC;
    let installs = find_installs(&[]);
    let mut checked = 0;
    for game in [Game::K1, Game::K2] {
        let Some(install) = installs.iter().find(|i| i.game == game) else { continue };
        let data = GameData::open(game, &install.path);
        let resref = data.resource_names("utc", RES_TYPE_UTC).into_iter().next().expect("no creature templates");
        let utc = data.gff(&resref, "utc", RES_TYPE_UTC).unwrap();
        for folder in find_saves(&installs, game, &[]).into_iter().take(4) {
            let name = folder.path.file_name().unwrap().to_string_lossy().to_string();
            let work = scratch(&format!("spawn-{:?}-{}", game, name));
            copy_dir(&folder.path, &work);
            let backups = scratch(&format!("spawn-{:?}-{}-backups", game, name));
            let mut save = Save::open(&work).unwrap();
            let Some(git) = save.area_git() else { continue };
            let list = git.root.list(area::CREATURES).cloned().unwrap_or_default();
            let Some(donor) = list.first().cloned() else { continue };
            let count = list.len();

            let mut fresh = area::creature_from_template(&utc.root, Some(&donor));
            area::place_creature(&mut fresh, area::position(&donor), 0.5);
            let id_a = save.spawn_creature(fresh);
            let id_b = save.spawn_creature(area::copy_creature(&donor));
            save.write(&backups).unwrap();

            let again = Save::open(&work).unwrap();
            let creatures = again.area_git().unwrap().root.list(area::CREATURES).cloned().unwrap();
            assert_eq!(creatures.len(), count + 2, "{}: two creatures added", name);
            let a = creatures.iter().find(|c| c.int("ObjectId") == Some(id_a as i64)).expect("template creature");
            assert_eq!(a.int("CreatnScrptFird"), Some(0), "{}: spawn script still to run", name);
            assert!(a.get("TemplateResRef").is_none());
            let b = creatures.iter().find(|c| c.int("ObjectId") == Some(id_b as i64)).expect("copied creature");
            assert_eq!(b.string("Tag"), donor.string("Tag"));
            // Every creature's own id, and its items' ids, once only (perception lists name
            // other creatures by id; those are references, not owners).
            let mut all = Vec::new();
            for c in &creatures {
                all.extend(c.int("ObjectId"));
                for list in ["Equip_ItemList", "ItemList"] {
                    for item in c.list(list).cloned().unwrap_or_default() {
                        all.extend(item.int("ObjectId"));
                    }
                }
            }
            let n = all.len();
            all.sort();
            all.dedup();
            assert_eq!(all.len(), n, "{}: an object id owned twice among the creatures", name);
            checked += 1;
        }
    }
    eprintln!("spawned into {} saves", checked);
}

/// Recruiting from a template (Skip Ahead's companions): Carth from p_carth into copies of
/// KotOR 1 saves that do not have him; written and read back, he is there, recruited and
/// selectable, with his template's name tag.
#[test]
fn recruit_from_template_survives_a_write() {
    use kse_core::formats::erf::RES_TYPE_UTC;
    let installs = find_installs(&[]);
    let Some(install) = installs.iter().find(|i| i.game == Game::K1) else { return };
    let data = GameData::open(Game::K1, &install.path);
    let Some(carth) = data.gff("p_carth", "utc", RES_TYPE_UTC) else { return };
    let mut checked = 0;
    for folder in find_saves(&installs, Game::K1, &[]) {
        let name = folder.path.file_name().unwrap().to_string_lossy().to_string();
        let work = scratch(&format!("recruit-{}", name));
        copy_dir(&folder.path, &work);
        let backups = scratch(&format!("recruit-{}-backups", name));
        let mut save = Save::open(&work).unwrap();
        if save.npcs().contains(&2) && save.recruited(2) {
            continue;
        }
        save.recruit_from_template(2, &carth.root).unwrap();
        save.write(&backups).unwrap();
        let again = Save::open(&work).unwrap();
        assert!(again.recruited(2), "{}: Carth recruited", name);
        assert!(again.selectable(2), "{}: Carth selectable", name);
        assert_eq!(again.creature(Who::Npc(2)).and_then(|c| c.string("Tag")), carth.root.string("Tag"), "{}", name);
        checked += 1;
    }
    eprintln!("recruited into {} saves", checked);
}

/// Played-through stored copies (stored::played_through) of every KotOR 1 module, built
/// against a real save's current module: each is a readable archive of module.ifo, the .are
/// and the .git; every object a full struct with the struct id its list loader checks and an
/// ObjectId used once, below Mod_NextObjId0; every door and placeable of the game's .git
/// kept (nothing is removed without a "remove" list), creatures too.
#[test]
fn played_through_copies_of_every_module() {
    use kse_core::formats::erf::{Erf, RES_TYPE_GIT, RES_TYPE_IFO};
    use kse_core::formats::gff::Gff;
    let installs = find_installs(&[]);
    let Some(install) = installs.iter().find(|i| i.game == Game::K1) else { return };
    let data = GameData::open(Game::K1, &install.path);
    let Some(folder) = find_saves(&installs, Game::K1, &[]).into_iter().next() else { return };
    let save = Save::open(&folder.path).unwrap();
    let (ifo, base) = save.current_module_parts().unwrap();
    let mut built = 0;
    for module in kse_core::map::game_modules(&install.path) {
        let Some(game) = kse_core::map::game_git(&data, &module) else { continue };
        let Some(bytes) = kse_core::stored::played_through(&data, &module, &Default::default(), &ifo, &base) else { continue };
        let erf = Erf::read(&bytes).unwrap_or_else(|e| panic!("{}: {}", module, e));
        let git = Gff::read(&erf.resources.iter().find(|r| r.kind == RES_TYPE_GIT).unwrap().data).unwrap();
        let mifo = Gff::read(&erf.resources.iter().find(|r| r.kind == RES_TYPE_IFO).unwrap().data).unwrap();
        assert_eq!(mifo.root.int("Mod_IsSaveGame"), Some(1), "{}", module);
        assert!(git.root.get("UseTemplates").is_none(), "{}", module);
        let next = mifo.root.int("Mod_NextObjId0").unwrap();
        let mut ids = Vec::new();
        for (list, sid) in [("Creature List", 4), ("Door List", 8), ("Placeable List", 9), ("TriggerList", 1), ("SoundList", 6), ("StoreList", 11), ("Encounter List", 7), ("WaypointList", 5)] {
            let ours = git.root.list(list).cloned().unwrap_or_default();
            for o in &ours {
                assert_eq!(o.id, sid, "{} {}: struct id", module, list);
                if list != "WaypointList" {
                    assert!(o.get("TemplateResRef").is_none(), "{} {}: template field left", module, list);
                }
                let id = o.int("ObjectId").unwrap_or_else(|| panic!("{} {}: no ObjectId", module, list));
                assert!(id < next, "{} {}: id {} not below {}", module, list, id, next);
                ids.push(id);
            }
            let theirs = game.root.list(list).map(|l| l.len()).unwrap_or(0);
            assert!(ours.len() <= theirs, "{} {}: more objects than the game's", module, list);
            if list == "Door List" || list == "Placeable List" || list == "WaypointList" {
                assert_eq!(ours.len(), theirs, "{} {}: an object lost", module, list);
            }
        }
        let n = ids.len();
        ids.sort();
        ids.dedup();
        assert_eq!(ids.len(), n, "{}: an object id used twice", module);
        built += 1;
    }
    eprintln!("built {} played-through modules", built);
    assert!(built > 50);
}

/// Skip Ahead through every main chapter of KotOR 1 on each side, from a copy of a save on
/// the Endar Spire: written and read back, the dark side ends with the dark story (the
/// final choice 1, Bastila back in the party, Juhani never recruited, Carth gone), the light
/// side with the light one; the light run ends with more light side and the dark run with
/// more dark side than the save had; both runs end with more credits.
#[test]
fn skip_whole_game_on_each_side() {
    let installs = find_installs(&[]);
    let Some(install) = installs.iter().find(|i| i.game == Game::K1) else { return };
    let data = GameData::open(Game::K1, &install.path);
    let Some(folder) = find_saves(&installs, Game::K1, &[]).into_iter().find(|f| {
        Save::open(&f.path).map_or(false, |s| s.module_name().to_ascii_lowercase().starts_with("end_m01"))
    }) else {
        return;
    };
    let order = |m: &serde_json::Value| m.get("order").and_then(|v| v.as_i64()).unwrap_or(99);
    let mut path: Vec<serde_json::Value> = kse_core::questdb::milestones(Game::K1).into_iter().map(|(_, m)| m).filter(|m| order(m) <= 10).collect();
    path.sort_by_key(|m| order(m));
    assert_eq!(path.len(), 10);
    assert!(kse_core::questdb::side_matters(Game::K1, &path));
    for dark in [false, true] {
        let work = scratch(&format!("skip-side-{}", dark));
        copy_dir(&folder.path, &work);
        let backups = scratch(&format!("skip-side-{}-backups", dark));
        let mut save = Save::open(&work).unwrap();
        let (gold, align) = (save.party_int("PT_GOLD").unwrap_or(0), creature::alignment(save.player().unwrap()));
        kse_core::questdb::skip_through(&mut save, &data, &path, Some(1), dark).unwrap();
        save.write(&backups).unwrap();
        let again = Save::open(&work).unwrap();
        let globals = globals::list(&again.globals.as_ref().unwrap().root);
        let number = |n: &str| globals.iter().find(|g| g.name.eq_ignore_ascii_case(n)).map(|g| g.value.clone());
        assert_eq!(number("G_FinalChoice"), Some(GlobalValue::Number(if dark { 1 } else { 2 })), "dark {}", dark);
        assert_eq!(again.recruited(5), !dark, "Juhani, dark {}", dark);
        assert_eq!(again.recruited(2), !dark, "Carth, dark {}", dark);
        if dark {
            assert!(again.recruited(0), "Bastila rejoins on the dark side");
        }
        let now = creature::alignment(again.player().unwrap());
        assert!(if dark { now < align } else { now > align }, "alignment {} from {}, dark {}", now, align, dark);
        assert!(again.party_int("PT_GOLD").unwrap_or(0) > gold, "credits, dark {}", dark);
    }
}

/// Skip Ahead through every main chapter of KotOR 2 on each side, from a copy of a save on
/// Peragus: written and read back, the masters' count reaches 4, the XP reaches the full
/// run's, slot 6 is gone after the masters' meeting and slot 1 after Malachor; the light
/// side recruits slot 7, the dark side slot 10 instead; the player's gender picks slot 4 or
/// slot 11. Not seen in the game.
#[test]
fn skip_whole_k2_game_on_each_side() {
    let installs = find_installs(&[]);
    let Some(install) = installs.iter().find(|i| i.game == Game::K2) else { return };
    let data = GameData::open(Game::K2, &install.path);
    let Some(folder) = find_saves(&installs, Game::K2, &[]).into_iter().find(|f| {
        Save::open(&f.path).map_or(false, |s| s.module_name().to_ascii_lowercase().starts_with("101per"))
    }) else {
        return;
    };
    let order = |m: &serde_json::Value| m.get("order").and_then(|v| v.as_i64()).unwrap_or(99);
    let side = |m: &serde_json::Value| m.get("side_chapter").and_then(|v| v.as_bool()).unwrap_or(false);
    let mut path: Vec<serde_json::Value> = kse_core::questdb::milestones(Game::K2).into_iter().map(|(_, m)| m).filter(|m| !side(m)).collect();
    path.sort_by_key(|m| order(m));
    assert_eq!(path.len(), 10);
    assert!(kse_core::questdb::side_matters(Game::K2, &path));
    let xp_end = kse_core::questdb::rewards_of(Game::K2, "Malachor V").and_then(|r| r.get("xp_at_end").and_then(|v| v.as_i64())).unwrap();
    for dark in [false, true] {
        let work = scratch(&format!("skip-k2-side-{}", dark));
        copy_dir(&folder.path, &work);
        let backups = scratch(&format!("skip-k2-side-{}-backups", dark));
        let mut save = Save::open(&work).unwrap();
        let gold = save.party_int("PT_GOLD").unwrap_or(0);
        let female = save.player().and_then(|p| p.int("Gender")) == Some(1);
        // the prestige class that matches the base class (Guardian, Sentinel, Consular)
        let base = creature::classes(save.player().unwrap())[0].0;
        let pick = match base { 3 => 0, 5 => 1, _ => 2 };
        let prestige = if dark { kse_core::questdb::PRESTIGE_DARK[pick] } else { kse_core::questdb::PRESTIGE_LIGHT[pick] };
        let notes = kse_core::questdb::skip_through_with(&mut save, &data, &path, None, dark, Some(prestige), true).unwrap();
        save.write(&backups).unwrap();
        let again = Save::open(&work).unwrap();
        let globals = globals::list(&again.globals.as_ref().unwrap().root);
        let number = |n: &str| globals.iter().find(|g| g.name.eq_ignore_ascii_case(n)).map(|g| g.value.clone());
        assert_eq!(number("000_Jedi_Found"), Some(GlobalValue::Number(4)), "masters found, dark {}", dark);
        assert!(creature::experience(again.player().unwrap()) >= xp_end, "XP, dark {}", dark);
        assert!(!again.recruited(6), "slot 6 gone after the masters' meeting, dark {}", dark);
        assert!(!again.recruited(1), "slot 1 lost at Malachor, dark {}", dark);
        assert_eq!(again.recruited(7), !dark, "slot 7, dark {}", dark);
        assert_eq!(again.recruited(10), dark, "slot 10, dark {}", dark);
        assert_eq!(again.recruited(4), !female, "slot 4 by gender, dark {}", dark);
        assert_eq!(again.recruited(11), female, "slot 11 by gender, dark {}", dark);
        assert!(again.party_int("PT_GOLD").unwrap_or(0) > gold, "credits, dark {}", dark);
        // the three masters' teachings, the story's powers, the prestige class
        let p = again.player().unwrap();
        assert_eq!(number("G_PC_FORM"), Some(GlobalValue::Number(3)), "forms taught, dark {}", dark);
        let forms = creature::powers(p).into_iter().filter(|s| (258..=268).contains(s)).count();
        assert!(forms >= 3, "{} forms known, dark {}", forms, dark);
        assert!(creature::feats(p).contains(&205), "Force Chain, dark {}", dark);
        assert!(creature::powers(p).contains(&if dark { 177 } else { 180 }), "the enclave's power, dark {}", dark);
        assert_eq!(creature::classes(p).get(1).map(|c| c.0), Some(prestige), "prestige class, dark {}", dark);
        assert_eq!(number("000_Prestige"), Some(GlobalValue::Number(2)), "000_Prestige, dark {}", dark);
        // influence moved for the companions who end in the party
        assert!((0..12).filter(|&i| again.recruited(i)).any(|i| again.influence(i).map_or(false, |v| v != 50)), "influence, dark {}", dark);
        for n in notes.iter().filter(|n| !n.starts_with("Story value")) {
            eprintln!("K2 dark {}: {}", dark, n);
        }
    }
}

/// Nothing a real run gives once is given twice: a chapter applied a second time to the same
/// save (its quests closed, its purchases made, its story items held) pays at most a small
/// remainder (conversations no quest of the chapter marks done), in both games. A chapter whose
/// areas the save keeps (Dantooine, Telos): their loot was taken on the first pass.
#[test]
fn a_chapter_does_not_pay_twice() {
    let installs = find_installs(&[]);
    for (game, start, chapter) in [(Game::K1, "end_m01", "Dantooine"), (Game::K2, "101per", "Telos")] {
        let Some(install) = installs.iter().find(|i| i.game == game) else { continue };
        let data = GameData::open(game, &install.path);
        let Some(folder) = find_saves(&installs, game, &[]).into_iter().find(|f| {
            Save::open(&f.path).map_or(false, |s| s.module_name().to_ascii_lowercase().starts_with(start))
        }) else {
            continue;
        };
        let m = kse_core::questdb::milestones(game).into_iter().find(|(p, _)| p.eq_ignore_ascii_case(chapter)).map(|(_, m)| m).unwrap();
        let work = scratch(&format!("twice-{:?}", game));
        copy_dir(&folder.path, &work);
        let mut save = Save::open(&work).unwrap();
        let g0 = save.party_int("PT_GOLD").unwrap_or(0);
        kse_core::questdb::skip_through(&mut save, &data, &[m.clone()], Some(0), false).unwrap();
        let (g1, items1) = (save.party_int("PT_GOLD").unwrap_or(0), save.inventory().len());
        kse_core::questdb::skip_through(&mut save, &data, &[m.clone()], Some(0), false).unwrap();
        let g2 = save.party_int("PT_GOLD").unwrap_or(0);
        eprintln!("{:?} {}: first pass {} credits, second {}; items {} then {}", game, chapter, g1 - g0, g2 - g1, items1, save.inventory().len());
        assert!(g1 - g0 > 0, "{:?}: the first pass pays", game);
        assert!((g2 - g1) * 4 < (g1 - g0), "{:?}: the second pass pays {} of {}", game, g2 - g1, g1 - g0);
    }
}
