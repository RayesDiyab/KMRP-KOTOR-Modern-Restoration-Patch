use kse_core::creature;
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use kse_core::map::Area;
use kse_core::save::Save;
use std::path::PathBuf;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&a[1]);
    let data = GameData::open(identify(&root).unwrap_or(Game::K1), &root);
    let save = Save::open(&PathBuf::from(&a[2])).unwrap();
    let m = save.module_name().to_string();
    let git = save.area_git().unwrap().root.clone();
    let area = Area::build(&data, &m, &git, &|s| creature::name(s));
    let p = save.player().unwrap();
    let (x, y, z) = (p.float("XPosition").unwrap(), p.float("YPosition").unwrap(), p.float("ZPosition").unwrap());
    let cal = area.calibration.as_ref().unwrap();
    let (u, v) = cal.to_map(x, y);
    let back = cal.to_world(u, v);
    println!("player {:?} map {:?} back {:?} height {:?} standable {:?}", (x, y, z), (u, v), back, area.floor.height(x, y, z), area.floor.standable(x, y, z));
    for (du, dv) in [(0.02, 0.0), (-0.02, 0.0), (0.0, 0.02), (0.05, 0.0), (0.1, 0.0)] {
        let (wx, wy) = cal.to_world(u + du, v + dv);
        println!("  {:?} -> {:?} height {:?} standable {:?} nearest {:?}", (du, dv), (wx, wy), area.floor.height(wx, wy, z), area.floor.standable(wx, wy, z), area.floor.nearest(wx, wy, z, 1.5));
    }
}
