//! Development aid: copies a save and makes the edits that only KSE offered before
//! (equipment, party, class level, quest stage, time played, Min1HP, voice), for loading
//! in the game.
//!   cargo run --example kse_test_save -- <game folder> <save folder> <new save folder>
use kse_core::catalog::Catalog;
use kse_core::creature;
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
    let base = data.table("baseitems");
    let mut save = Save::open(&to).unwrap();

    // Equipment: take the gloves off, put another mask on.
    println!("gloves off: {}", save.unequip(Who::Player, 0x8));
    let inv = save.inventory();
    let mask = inv.iter().position(|it| {
        let b = it.int("BaseItem").unwrap_or(0) as usize;
        base.int(b, "equipableslots").map_or(false, |m| m & 0x1 != 0) && base.int(b, "droidorhuman") != Some(2)
    });
    if let Some(i) = mask {
        println!("mask on: {:?} {}", inv[i].string("Tag"), save.equip(Who::Player, 0x1, i));
    }
    // Party: two recruited members along.
    let now = save.party_members();
    let members: Vec<usize> = save.npcs().into_iter().filter(|n| save.recruited(*n) && !now.contains(n)).take(2).collect();
    println!("party before {:?}", now);
    println!("party {:?}: {:?}", members, save.set_party_members(&members));
    // One more level in the last class.
    let classes = creature::classes(save.player().unwrap());
    let index = classes.len() - 1;
    let (id, lv) = classes[index];
    let class = cat.class(id).unwrap().clone();
    let xp = |l: i64| cat.xp_for(l);
    save.edit(Who::Player, "level", |c| creature::set_class_level(c, index, lv + 1, &class, &xp));
    println!("level {} -> {}", lv, creature::classes(save.player().unwrap())[index].1);
    // A quest stage, time played, Min1HP, voice.
    if let Some((tag, stage)) = save.quests().first().cloned() {
        save.set_quest(&tag, stage);
        println!("quest {} stays at {}", tag, stage);
    }
    save.set_party_int("PT_PLAYEDSECONDS", 99 * 3600 + 30 * 60);
    save.edit(Who::Player, "min1hp", |c| creature::set_min1hp(c, true));
    save.edit(Who::Player, "voice", |c| creature::set_soundset(c, 85));
    save.edit_nfo(|n| n.set("SAVEGAMENAME", Value::String(b"KSE Features Test".to_vec())));
    let backups = std::env::temp_dir().join("kmrp-save-editor-tests").join("kse-backups");
    save.write(&backups).unwrap();
    let back = Save::open(&to).unwrap();
    let p = back.player().unwrap();
    println!("read back: slots {:?}, party {:?}, level {:?}, min1hp {}, played {:?}",
        creature::equipped(p).iter().map(|i| i.id).collect::<Vec<_>>(), back.party_members(),
        creature::classes(p), creature::min1hp(p), back.party_int("PT_PLAYEDSECONDS"));
    println!("written {}", to.display());
}
