//! Development aid: an area's map calibration, layout, first walkmesh header and plot.2da.
//!   cargo run --example area_probe -- <game folder> <module> <area>
use kse_core::formats::gff::Gff;
use kse_core::formats::rim::Rim;
use kse_core::formats::tables::find_case_insensitive;
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&args[1]);
    let game = identify(&root).unwrap_or(Game::K1);
    let data = GameData::open(game, &root);
    let rim = Rim::open(&find_case_insensitive(&root, &format!("modules/{}.rim", args[2])).unwrap()).unwrap();
    let are = Gff::read(&rim.read(&args[3], 2012).unwrap()).unwrap();
    if let Some(m) = are.root.child("Map") {
        for (l, v) in &m.fields {
            println!("Map.{} = {:?}", l, v);
        }
    }
    let lyt = data.resource(&args[3], "lyt", 3000).map(|b| String::from_utf8_lossy(&b).to_string()).unwrap_or_default();
    println!("lyt:\n{}", lyt.lines().take(8).collect::<Vec<_>>().join("\n"));
    let rooms: Vec<String> = lyt.lines().filter(|l| l.trim_start().split_whitespace().count() == 4 && !l.contains("count")).map(|l| l.split_whitespace().next().unwrap().to_string()).collect();
    for room in rooms {
        let Some(wok) = data.resource(&room, "wok", 2016) else { println!("{} no wok", room); continue };
        if wok.len() <= 136 { println!("{} empty", room); continue; }
        println!("wok {} bytes, head {:?}", wok.len(), String::from_utf8_lossy(&wok[0..8]));
        let f = |o: usize| f32::from_le_bytes(wok[o..o + 4].try_into().unwrap());
        let u = |o: usize| u32::from_le_bytes(wok[o..o + 4].try_into().unwrap());
        println!("type {} pos {:?} verts {} @{} faces {} @{} mats @{}", u(8), (f(60), f(64), f(68)), u(72), u(76), u(80), u(84), u(88));
        let vo = u(76) as usize;
        println!("first vertex {:?}", (f(vo), f(vo + 4), f(vo + 8)));
    }
    let plot = data.table("plot");
    println!("plot columns {:?} rows {}", plot.columns, plot.rows.len());
    for r in 0..3.min(plot.rows.len()) {
        println!("  {:?}", plot.rows[r]);
    }
    let sm = data.table("surfacemat");
    println!("surfacemat columns {:?}", &sm.columns[..sm.columns.len().min(6)]);
    for r in 0..sm.rows.len() {
        print!("{}:{} ", sm.cell(r, "label").unwrap_or(""), sm.cell(r, "walk").unwrap_or("-"));
    }
    println!();
}
