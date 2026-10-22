//! Development aid: copies a save to a new save slot and queues a trip to another area,
//! for loading in the game (save::Save::queue_transition).
//!   cargo run --example travel_test -- <save folder> <new save folder> <module> <waypoint> <save name>
use kse_core::save::Save;
use std::fs;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let from = PathBuf::from(&args[1]);
    let to = PathBuf::from(&args[2]);
    fs::create_dir_all(&to).unwrap();
    for e in fs::read_dir(&from).unwrap().filter_map(|e| e.ok()) {
        if e.path().is_file() {
            fs::copy(e.path(), to.join(e.file_name())).unwrap();
        }
    }
    let mut save = Save::open(&to).unwrap();
    save.queue_transition(&args[3], &args[4], &[]).unwrap();
    save.rename(&args[5]);
    let backups = std::env::temp_dir().join("kmrp-travel-test-backups");
    save.write(&backups).unwrap();
    println!("written {}", to.display());
}
