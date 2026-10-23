//! Development aid: writes the played-through stored copy of a module (stored::played_through,
//! nothing removed) to a file, to compare with a copy the game itself stored.
//!   cargo run --example stored_dump -- <game folder> <save folder> <module> <out file>
use kse_core::gamedata::GameData;
use kse_core::games::Game;
use kse_core::save::Save;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let data = GameData::open(Game::K1, &PathBuf::from(&args[1]));
    let save = Save::open(&PathBuf::from(&args[2])).unwrap();
    let (ifo, base) = save.current_module_parts().unwrap();
    let bytes = kse_core::stored::played_through(&data, &args[3], &Default::default(), &ifo, &base).unwrap();
    std::fs::write(&args[4], bytes).unwrap();
}
