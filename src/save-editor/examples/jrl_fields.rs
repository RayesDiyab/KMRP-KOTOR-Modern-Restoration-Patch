//! Development aid: prints the fields of the game's journal (global.jrl): one quest and
//! its stages.
//!   cargo run --example jrl_fields -- <game folder>
use kse_core::formats::gff::Value;
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use std::path::PathBuf;

fn main() {
    let root = PathBuf::from(std::env::args().nth(1).unwrap());
    let game = identify(&root).unwrap_or(Game::K1);
    let data = GameData::open(game, &root);
    let jrl = data.gff("global", "jrl", 2056).expect("no global.jrl");
    let cats = jrl.root.list("Categories").unwrap();
    println!("{} quests", cats.len());
    for c in cats.iter().take(3) {
        let fields: Vec<String> = c
            .fields
            .iter()
            .filter(|(l, _)| l != "EntryList")
            .map(|(l, v)| match v {
                Value::LocString(x) => format!("{}={}", l, data.loc(x)),
                other => format!("{}={:?}", l, other),
            })
            .collect();
        println!("quest: {}", fields.join(", "));
        for e in c.list("EntryList").unwrap().iter().take(4) {
            let f: Vec<String> = e
                .fields
                .iter()
                .map(|(l, v)| match v {
                    Value::LocString(x) => format!("{}={:.40}", l, data.loc(x)),
                    other => format!("{}={:?}", l, other),
                })
                .collect();
            println!("   stage: {}", f.join(", "));
        }
    }
}
