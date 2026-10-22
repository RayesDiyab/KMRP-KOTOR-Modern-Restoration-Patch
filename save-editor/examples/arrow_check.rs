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
    let area = Area::build(&data, &m, &save.area_git().unwrap().root, &|s| creature::name(s));
    let p = save.player().unwrap();
    let pos = kse_core::area::position(p);
    let (fx, fy) = (p.float("XOrientation").unwrap(), p.float("YOrientation").unwrap());
    let (u, v) = area.to_map(pos[0], pos[1]).unwrap();
    let (au, av) = area.to_map(pos[0] + fx, pos[1] + fy).unwrap();
    println!("facing {:?} angle {:.0} deg clockwise from up", (fx, fy), (au - u).atan2(-(av - v)).to_degrees());
}
