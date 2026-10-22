use kse_core::formats::{tga, tpc};
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use std::path::PathBuf;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&a[1]);
    let data = GameData::open(identify(&root).unwrap_or(Game::K1), &root);
    let (b, is_tpc) = data.texture(&a[2]).expect("no texture");
    let img = if is_tpc { tpc::decode(&b) } else { tga::decode(&b) }.unwrap();
    println!("{} {}x{} tpc={}", a[2], img.width, img.height, is_tpc);
    let mut out = vec![0u8; 18];
    out[2] = 2;
    out[12..14].copy_from_slice(&(img.width as u16).to_le_bytes());
    out[14..16].copy_from_slice(&(img.height as u16).to_le_bytes());
    out[16] = 32;
    out[17] = 0x28;
    for c in img.rgba.chunks(4) { out.extend_from_slice(&[c[2], c[1], c[0], c[3]]); }
    std::fs::write(&a[3], out).unwrap();
}
