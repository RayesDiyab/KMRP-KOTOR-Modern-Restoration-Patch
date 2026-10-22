//! Development aid: two copies of a save for loading in the game, one with the player
//! moved within the area (next to a person), one moved into another area the save has been
//! to (next to a way out there).
//!   cargo run --example map_test_save -- <game folder> <save folder> <saves folder>
use kse_core::creature;
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use kse_core::map::{Area, Kind};
use kse_core::save::Save;
use std::fs;
use std::path::PathBuf;

fn copy(from: &PathBuf, to: &PathBuf) {
    let _ = fs::remove_dir_all(to);
    fs::create_dir_all(to).unwrap();
    for e in fs::read_dir(from).unwrap().filter_map(|e| e.ok()) {
        fs::copy(e.path(), to.join(e.file_name())).unwrap();
    }
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&a[1]);
    let from = PathBuf::from(&a[2]);
    let saves = PathBuf::from(&a[3]);
    let data = GameData::open(identify(&root).unwrap_or(Game::K1), &root);
    let backups = std::env::temp_dir().join("kmrp-save-editor-tests").join("map-backups");

    let here = saves.join("000097 - Map Move Here");
    copy(&from, &here);
    let mut save = Save::open(&here).unwrap();
    let m = save.module_name().to_string();
    let area = Area::build(&data, &m, &save.area_git().unwrap().root, &|s| creature::name(s));
    let target = area.objects.iter().filter(|o| !o.spots.is_empty()).max_by(|x, y| {
        let p = creature::name(save.player().unwrap());
        let _ = p;
        (x.pos[0].abs() + x.pos[1].abs()).partial_cmp(&(y.pos[0].abs() + y.pos[1].abs())).unwrap()
    });
    let o = target.unwrap();
    let spot = o.spots[0];
    save.move_player(spot, Some((o.pos[1] - spot[1]).atan2(o.pos[0] - spot[0])));
    save.rename("Map Move Here");
    save.write(&backups).unwrap();
    println!("moved within {} next to {:?} ({:?}) at {:?}", area.name, o.name, o.kind, spot);

    let there = saves.join("000098 - Map Other Area");
    copy(&from, &there);
    let mut save = Save::open(&there).unwrap();
    let current = save.module_name().to_ascii_lowercase();
    let other = save.visited_modules().into_iter().find(|v| *v != current).expect("no other area visited");
    let git = save.module_git(&other).unwrap();
    let area = Area::build(&data, &other, &git.root, &|s| creature::name(s));
    let o = area.objects.iter().find(|o| o.kind == Kind::Exit && !o.spots.is_empty()).or_else(|| area.objects.iter().find(|o| !o.spots.is_empty())).unwrap();
    let spot = o.spots[0];
    save.move_to_module(&other, spot, &area.name).unwrap();
    // A known facing to compare with the game's map arrow: world +X.
    save.move_player(spot, Some(0.0));
    save.rename("Map Other Area");
    save.write(&backups).unwrap();
    println!("moved to {} ({}) next to {:?} at {:?}", area.name, other, o.name, spot);
}
