//! Development aid: draws a save's current area map with its objects, their safe spots and
//! the player, into a TGA, and prints what it found.
//!   cargo run --example map_probe -- <game folder> <save folder> <out.tga>
use kse_core::creature;
use kse_core::gamedata::GameData;
use kse_core::games::{identify, Game};
use kse_core::map::{Area, Kind};
use kse_core::save::Save;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&args[1]);
    let game = identify(&root).unwrap_or(Game::K1);
    let data = GameData::open(game, &root);
    let save = Save::open(&PathBuf::from(&args[2])).unwrap();
    let module = save.nfo.root.string("LASTMODULE").unwrap();
    let git = save.area_git().unwrap().root.clone();
    let area = Area::build(&data, &module, &git, &|s| creature::name(s));
    let p = save.player().unwrap();
    let pp = [p.float("XPosition").unwrap(), p.float("YPosition").unwrap(), p.float("ZPosition").unwrap()];
    println!("{} ({}) floor tris empty={} picture={:?}", area.name, area.area, area.floor.is_empty(), area.picture.as_ref().map(|i| (i.width, i.height)));
    println!("player at {:?}: on floor {:?}", pp, area.floor.height(pp[0], pp[1], pp[2]));
    let mut kinds = std::collections::BTreeMap::new();
    for o in &area.objects {
        kinds.entry(format!("{:?}", o.kind)).or_insert((0, 0)).0 += 1;
        if !o.spots.is_empty() {
            kinds.get_mut(&format!("{:?}", o.kind)).unwrap().1 += 1;
        }
        if o.kind == Kind::Exit {
            println!("  exit {:?} -> {} ({} spots)", o.name, o.leads_to, o.spots.len());
        }
    }
    println!("objects (count, with a spot): {:?}", kinds);
    let Some(img) = area.picture.as_ref() else { return };
    let (w, h) = (img.width as usize, img.height as usize);
    let mut px = img.rgba.clone();
    // The picture's map part is 440/512 of the width (KotOR 1's 512x256 textures).
    let mw = w as f32 * 440.0 / 512.0;
    let mut dot = |u: f32, v: f32, c: [u8; 3], r: i32| {
        let (cx, cy) = ((u * mw) as i32, (v * h as f32) as i32);
        for dy in -r..=r {
            for dx in -r..=r {
                let (x, y) = (cx + dx, cy + dy);
                if x >= 0 && y >= 0 && (x as usize) < w && (y as usize) < h {
                    let o = (y as usize * w + x as usize) * 4;
                    px[o..o + 3].copy_from_slice(&c);
                    px[o + 3] = 255;
                }
            }
        }
    };
    for o in &area.objects {
        let c = match o.kind {
            Kind::Door => [255, 255, 0],
            Kind::Exit => [255, 0, 255],
            Kind::Container | Kind::Placeable => [0, 255, 0],
            Kind::Creature | Kind::Merchant => [255, 80, 0],
            Kind::Note => [255, 255, 255],
        };
        if let Some((u, v)) = area.to_map(o.pos[0], o.pos[1]) {
            dot(u, v, c, 2);
        }
        for s in &o.spots {
            if let Some((u, v)) = area.to_map(s[0], s[1]) {
                dot(u, v, [0, 200, 255], 1);
            }
        }
    }
    if let Some((u, v)) = area.to_map(pp[0], pp[1]) {
        dot(u, v, [255, 0, 0], 3);
    }
    let mut out = vec![0u8; 18];
    out[2] = 2;
    out[12..14].copy_from_slice(&(w as u16).to_le_bytes());
    out[14..16].copy_from_slice(&(h as u16).to_le_bytes());
    out[16] = 32;
    out[17] = 0x28;
    for c in px.chunks(4) {
        out.extend_from_slice(&[c[2], c[1], c[0], c[3]]);
    }
    std::fs::write(&args[3], out).unwrap();
}
