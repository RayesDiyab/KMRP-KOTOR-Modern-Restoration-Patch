//! Development aid: prints a table's columns and first rows from an install.
//!   cargo run --example dump2da -- <game folder> <table> [rows]
use kse_core::games::{identify, Game};
use kse_core::gamedata::GameData;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&args[1]);
    let game = identify(&root).unwrap_or(Game::K1);
    let data = GameData::open(game, &root);
    let t = data.table(&args[2]);
    let rows: usize = args.get(3).and_then(|r| r.parse().ok()).unwrap_or(5);
    println!("{:?} {} rows, columns: {:?}", game, t.rows.len(), t.columns);
    for r in 0..rows.min(t.rows.len()) {
        println!("{} {:?} | {:?}", r, data.row_name(&args[2], r), t.rows[r]);
    }
}
