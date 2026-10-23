//! Development aid: copies a save to a new save slot and skips it to the end of a chapter
//! the editor has a milestone for (questdb::skip_to), for loading in the game.
//!   cargo run --example skip_test -- <game folder> <save folder> <new save folder> <planet> <save name> [dark]
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use kse_core::save::Save;
use std::fs;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let game_dir = PathBuf::from(&args[1]);
    let (from, to) = (PathBuf::from(&args[2]), PathBuf::from(&args[3]));
    fs::create_dir_all(&to).unwrap();
    for e in fs::read_dir(&from).unwrap().filter_map(|e| e.ok()) {
        if e.path().is_file() {
            fs::copy(e.path(), to.join(e.file_name())).unwrap();
        }
    }
    let game = identify(&game_dir).unwrap_or(Game::K1);
    let data = GameData::open(game, &game_dir);
    // Every main chapter up to the one named, in story order (as the editor's Skip to Here
    // does for a save that has played none of them); a Jedi Guardian on Dantooine.
    let all = kse_core::questdb::milestones(game);
    let order = |m: &serde_json::Value| m.get("order").and_then(|v| v.as_i64()).unwrap_or(1);
    let target = all.iter().find(|(p, _)| p.eq_ignore_ascii_case(&args[4])).map(|(_, m)| order(m)).expect("no such milestone");
    let mut path: Vec<serde_json::Value> = all.iter().map(|(_, m)| m.clone()).filter(|m| order(m) <= target && order(m) <= 10).collect();
    path.sort_by_key(|m| order(m));
    let mut save = Save::open(&to).unwrap();
    for note in kse_core::questdb::skip_through(&mut save, &data, &path, Some(0), args.get(6).map_or(false, |a| a == "dark")).unwrap() {
        println!("note: {}", note);
    }
    save.rename(&args[5]);
    save.write(&std::env::temp_dir().join("kmrp-skip-test-backups")).unwrap();
    println!("written {}", to.display());
}
