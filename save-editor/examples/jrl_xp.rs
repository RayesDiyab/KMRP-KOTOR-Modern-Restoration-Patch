use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use std::path::PathBuf;
fn main() {
    let root = PathBuf::from(std::env::args().nth(1).unwrap());
    let data = GameData::open(identify(&root).unwrap_or(Game::K1), &root);
    let jrl = data.gff("global", "jrl", 2056).unwrap();
    let plot = data.table("plot");
    let mut shown = 0;
    for c in jrl.root.list("Categories").unwrap() {
        let pi = c.int("PlotIndex").unwrap_or(-1);
        let stages: Vec<(i64, i64, f32)> = c.list("EntryList").unwrap().iter().map(|e| (e.int("ID").unwrap_or(0), e.int("End").unwrap_or(0), e.float("XP_Percentage").unwrap_or(0.0))).collect();
        if stages.iter().any(|s| s.2 != 0.0) && shown < 6 {
            println!("{} plot {} xp {:?}: {:?}", c.string("Tag").unwrap_or_default(), pi, plot.int(pi.max(0) as usize, "xp"), stages);
            shown += 1;
        }
    }
}
