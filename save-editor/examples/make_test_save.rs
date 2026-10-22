//! Development aid: copies a save to a new folder and makes visible changes through the
//! editor's library, for loading in the game.
//!   cargo run --example make_test_save -- <game folder> <save folder> <new save folder>
use kse_core::catalog::{self, Catalog};
use kse_core::creature;
use kse_core::formats::erf::RES_TYPE_UTI;
use kse_core::formats::gff::Value;
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use kse_core::save::{Save, Who};
use std::fs;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let game_dir = PathBuf::from(&args[1]);
    let from = PathBuf::from(&args[2]);
    let to = PathBuf::from(&args[3]);
    let _ = fs::remove_dir_all(&to);
    fs::create_dir_all(&to).unwrap();
    for e in fs::read_dir(&from).unwrap().filter_map(|e| e.ok()) {
        fs::copy(e.path(), to.join(e.file_name())).unwrap();
    }
    let game = identify(&game_dir).unwrap_or(Game::K1);
    let data = GameData::open(game, &game_dir);
    let cat = Catalog::build(&data);
    let mut save = Save::open(&to).unwrap();
    save.edit(Who::Player, "name", |c| creature::set_name(c, "Kmrp Tester"));
    save.edit(Who::Player, "Str", |c| creature::set_attribute(c, "Str", 24));
    save.edit(Who::Player, "Cha", |c| creature::set_attribute(c, "Cha", 16));
    save.edit(Who::Player, "skill0", |c| creature::set_skill(c, 0, 14));
    let flurry = cat.feats.iter().find(|f| f.name.contains("Master Flurry") || f.name.contains("Meister")).map(|f| f.id);
    if let Some(f) = flurry {
        save.edit(Who::Player, "feat", |c| {
            creature::add_feat(c, f);
        });
    }
    let powers = creature::powers(save.player().unwrap());
    if let Some(&p) = powers.first() {
        println!("removing power {}", cat.power_name(p));
        save.edit(Who::Player, "power", |c| {
            creature::remove_power(c, p);
        });
    }
    let lightning = cat.powers.iter().find(|p| p.name.contains("Lightning") || p.name.contains("Blitz")).map(|p| p.id);
    if let Some(p) = lightning {
        save.edit(Who::Player, "power+", |c| {
            creature::add_power(c, p, &|k| cat.is_force_class(k));
        });
    }
    save.edit(Who::Player, "heal", creature::heal);
    save.set_party_int("PT_GOLD", 424242);
    let templates = catalog::item_templates(&data);
    let like = save.inventory().first().cloned();
    for wanted in ["g_w_lghtsbr03", "g_i_medeqpmnt03"] {
        if let Some(t) = templates.iter().find(|t| t.resref == wanted) {
            let uti = data.gff(&t.resref, "uti", RES_TYPE_UTI).unwrap();
            let item = catalog::item_from_template(&uti.root, like.as_ref(), 3);
            println!("adding {}", t.name);
            save.edit_inventory("add", |items| items.push(item.clone()));
        }
    }
    if let Some(n) = save.npcs().first().copied() {
        save.edit(Who::Npc(n), "Con", |c| creature::set_attribute(c, "Con", 20));
    }
    save.edit_nfo(|n| n.set("SAVEGAMENAME", Value::String(b"KMRP Edit Test".to_vec())));
    let backups = std::env::temp_dir().join("kmrp-save-editor-tests").join("example-backups");
    save.write(&backups).unwrap();
    println!("written {}", to.display());
}
