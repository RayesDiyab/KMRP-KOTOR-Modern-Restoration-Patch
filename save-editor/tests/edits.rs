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
