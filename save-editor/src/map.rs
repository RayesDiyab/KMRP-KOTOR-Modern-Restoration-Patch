//! An area as a map: its picture and calibration (the .are's Map struct), its floor (the
//! rooms' walkmeshes named in the .lyt), the objects the save puts in it (the .git), and
//! the areas its doors and exits lead to. Safe places to stand are found on the floor.
//!
//! World to map, as the game does it (reverse-engineering/map-scaling.md): the area's
//! two calibration points give a scale per axis; NorthAxis 2 and 3 swap the axes. The
//! result is a fraction of the picture's 440 x 256 part of the 512 x 256 texture.

use crate::formats::gff::{Gff, Struct, Value};
use crate::formats::rim::Rim;
use crate::formats::tables::find_case_insensitive;
use crate::gamedata::GameData;
use std::path::Path;

#[derive(Clone, Debug, Default)]
pub struct Calibration {
    north: i64,
    world1: (f32, f32),
    world2: (f32, f32),
    map1: (f32, f32),
    map2: (f32, f32),
}

impl Calibration {
    pub fn from_are(are: &Struct) -> Option<Calibration> {
        let m = are.child("Map")?;
        let f = |l: &str| m.float(l).unwrap_or(0.0);
        Some(Calibration {
            north: m.int("NorthAxis").unwrap_or(0),
            world1: (f("WorldPt1X"), f("WorldPt1Y")),
            world2: (f("WorldPt2X"), f("WorldPt2Y")),
            map1: (f("MapPt1X"), f("MapPt1Y")),
            map2: (f("MapPt2X"), f("MapPt2Y")),
        })
    }

    fn swapped(&self) -> bool {
        self.north == 2 || self.north == 3
    }

    /// World position to a fraction of the map picture (0..1 each way).
    pub fn to_map(&self, x: f32, y: f32) -> (f32, f32) {
        let (a, b) = if self.swapped() { (y, x) } else { (x, y) };
        let (w1a, w1b, w2a, w2b) = if self.swapped() {
            (self.world1.1, self.world1.0, self.world2.1, self.world2.0)
        } else {
            (self.world1.0, self.world1.1, self.world2.0, self.world2.1)
        };
        let sx = (self.map1.0 - self.map2.0) / (w1a - w2a);
        let sy = (self.map1.1 - self.map2.1) / (w1b - w2b);
        ((a - w1a) * sx + self.map1.0, (b - w1b) * sy + self.map1.1)
    }

    /// A fraction of the map picture back to a world position.
    pub fn to_world(&self, u: f32, v: f32) -> (f32, f32) {
        let (w1a, w1b, w2a, w2b) = if self.swapped() {
            (self.world1.1, self.world1.0, self.world2.1, self.world2.0)
        } else {
            (self.world1.0, self.world1.1, self.world2.0, self.world2.1)
        };
        let sx = (self.map1.0 - self.map2.0) / (w1a - w2a);
        let sy = (self.map1.1 - self.map2.1) / (w1b - w2b);
        let a = (u - self.map1.0) / sx + w1a;
        let b = (v - self.map1.1) / sy + w1b;
        if self.swapped() {
            (b, a)
        } else {
            (a, b)
        }
    }
}

/// The floor: every walkable triangle of every room.
#[derive(Default)]
pub struct Floor {
    tris: Vec<[[f32; 3]; 3]>,
}

fn u32_at(d: &[u8], o: usize) -> Option<u32> {
    d.get(o..o + 4).map(|b| u32::from_le_bytes(b.try_into().unwrap()))
}

fn f32_at(d: &[u8], o: usize) -> Option<f32> {
    d.get(o..o + 4).map(|b| f32::from_le_bytes(b.try_into().unwrap()))
}

impl Floor {
    /// Adds a room's walkmesh (BWM V1.0; an area's vertices are in world coordinates).
    pub fn add_bwm(&mut self, data: &[u8], walkable: &dyn Fn(u32) -> bool) {
        if data.get(0..8) != Some(b"BWM V1.0") || data.len() <= 136 {
            return;
        }
        let (Some(vn), Some(vo), Some(fnum), Some(fo), Some(mo)) =
            (u32_at(data, 72), u32_at(data, 76), u32_at(data, 80), u32_at(data, 84), u32_at(data, 88))
        else {
            return;
        };
        let vert = |i: u32| -> Option<[f32; 3]> {
            if i >= vn {
                return None;
            }
            let o = vo as usize + i as usize * 12;
            Some([f32_at(data, o)?, f32_at(data, o + 4)?, f32_at(data, o + 8)?])
        };
        for f in 0..fnum as usize {
            let Some(mat) = u32_at(data, mo as usize + f * 4) else { break };
            if !walkable(mat) {
                continue;
            }
            let o = fo as usize + f * 12;
            let (Some(a), Some(b), Some(c)) = (u32_at(data, o), u32_at(data, o + 4), u32_at(data, o + 8)) else { break };
            if let (Some(a), Some(b), Some(c)) = (vert(a), vert(b), vert(c)) {
                self.tris.push([a, b, c]);
            }
        }
    }

    pub fn is_empty(&self) -> bool {
        self.tris.is_empty()
    }

    /// The floor's height at (x, y), when (x, y) is on walkable floor. Where floors
    /// overlap (stairs, balconies), the one nearest `near_z`.
    pub fn height(&self, x: f32, y: f32, near_z: f32) -> Option<f32> {
        let mut best: Option<f32> = None;
        for t in &self.tris {
            let (x1, y1, x2, y2, x3, y3) = (t[0][0], t[0][1], t[1][0], t[1][1], t[2][0], t[2][1]);
            let d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3);
            if d.abs() < 1e-9 {
                continue;
            }
            let l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d;
            let l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d;
            let l3 = 1.0 - l1 - l2;
            if l1 < -1e-4 || l2 < -1e-4 || l3 < -1e-4 {
                continue;
            }
            let z = l1 * t[0][2] + l2 * t[1][2] + l3 * t[2][2];
            if best.map_or(true, |b| (z - near_z).abs() < (b - near_z).abs()) {
                best = Some(z);
            }
        }
        best
    }

    /// Whether a character can stand at (x, y): floor under it and under a ring around
    /// it, so the spot is not at the edge of a wall or a drop.
    pub fn standable(&self, x: f32, y: f32, near_z: f32) -> Option<f32> {
        let z = self.height(x, y, near_z)?;
        const R: f32 = 0.45;
        for (dx, dy) in [(R, 0.0), (-R, 0.0), (0.0, R), (0.0, -R), (0.7 * R, 0.7 * R), (-0.7 * R, 0.7 * R), (0.7 * R, -0.7 * R), (-0.7 * R, -0.7 * R)] {
            let h = self.height(x + dx, y + dy, z)?;
            if (h - z).abs() > 0.6 {
                return None;
            }
        }
        Some(z)
    }

    /// The standable spot nearest (x, y), searched outwards to `radius`.
    pub fn nearest(&self, x: f32, y: f32, near_z: f32, radius: f32) -> Option<[f32; 3]> {
        if let Some(z) = self.standable(x, y, near_z) {
            return Some([x, y, z]);
        }
        let mut r = 0.25;
        while r <= radius {
            for k in 0..16 {
                let a = k as f32 * std::f32::consts::TAU / 16.0;
                let (px, py) = (x + r * a.cos(), y + r * a.sin());
                if let Some(z) = self.standable(px, py, near_z) {
                    return Some([px, py, z]);
                }
            }
            r += 0.25;
        }
        None
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Door,
    Exit,
    Container,
    Placeable,
    Creature,
    Merchant,
    Note,
}

#[derive(Clone, Debug)]
pub struct Object {
    pub kind: Kind,
    /// The .git list and index it came from.
    pub list: &'static str,
    pub index: usize,
    pub name: String,
    pub tag: String,
    pub pos: [f32; 3],
    /// Facing, radians.
    pub facing: f32,
    /// For doors and exits: the module they lead to.
    pub leads_to: String,
    pub locked: bool,
    /// Places to stand next to it (two for a door, one a side).
    pub spots: Vec<[f32; 3]>,
    /// A person's portrait (portraits.2da row), when they have one.
    pub portrait: Option<i64>,
}

/// A place to stand by `pos` facing `facing`: in front first, then round the sides, a
/// little further out each time, on floor with room around it.
fn spot_by(floor: &Floor, pos: [f32; 3], facing: f32, start: f32) -> Option<[f32; 3]> {
    for dist in [start, start + 0.4, start + 0.8, start + 1.3] {
        for turn in [0.0f32, 0.5, -0.5, 1.0, -1.0, 1.57, -1.57, 2.2, -2.2, 3.14] {
            let a = facing + turn;
            let (x, y) = (pos[0] + dist * a.cos(), pos[1] + dist * a.sin());
            if let Some(z) = floor.standable(x, y, pos[2]) {
                return Some([x, y, z]);
            }
        }
    }
    None
}

/// A door's two sides: in front and behind, along the way through it.
fn door_sides(floor: &Floor, pos: [f32; 3], bearing: f32) -> Vec<[f32; 3]> {
    let mut out = Vec::new();
    for base in [bearing + std::f32::consts::FRAC_PI_2, bearing - std::f32::consts::FRAC_PI_2] {
        for dist in [1.2f32, 1.6, 2.0, 2.6] {
            let (x, y) = (pos[0] + dist * base.cos(), pos[1] + dist * base.sin());
            if let Some(z) = floor.standable(x, y, pos[2]) {
                out.push([x, y, z]);
                break;
            }
        }
    }
    out
}

pub struct Area {
    pub module: String,
    pub area: String,
    pub name: String,
    pub calibration: Option<Calibration>,
    pub picture: Option<crate::formats::tga::Image>,
    pub floor: Floor,
    pub objects: Vec<Object>,
}

/// The area files of a module as the game finds them: a .mod (from a mod) first, then the
/// module's .rim and _s.rim.
pub struct ModuleFiles {
    rims: Vec<Rim>,
    erf: Option<crate::formats::erf::Erf>,
}

impl ModuleFiles {
    pub fn open(root: &Path, module: &str) -> ModuleFiles {
        let erf = find_case_insensitive(root, &format!("modules/{}.mod", module))
            .and_then(|p| std::fs::read(p).ok())
            .and_then(|d| crate::formats::erf::Erf::read(&d).ok());
        let rims = [".rim", "_s.rim"]
            .iter()
            .filter_map(|s| find_case_insensitive(root, &format!("modules/{}{}", module, s)))
            .filter_map(|p| Rim::open(&p))
            .collect();
        ModuleFiles { rims, erf }
    }

    pub fn read(&self, name: &str, kind: u16) -> Option<Vec<u8>> {
        if let Some(r) = self.erf.as_ref().and_then(|e| e.find(name, kind)) {
            return Some(r.data.clone());
        }
        self.rims.iter().find_map(|r| r.read(name, kind))
    }

    /// The module's area: the .are named in its Module.ifo.
    pub fn area_name(&self) -> Option<String> {
        let ifo = Gff::read(&self.read("module", crate::formats::erf::RES_TYPE_IFO)?).ok()?;
        let list = ifo.root.list("Mod_Area_list")?;
        list.first()?.string("Area_Name")
    }
}

fn loc_name(data: &GameData, s: &Struct, label: &str) -> String {
    match s.get(label) {
        Some(Value::LocString(l)) => crate::text::strip_codes(&data.loc(l)),
        _ => String::new(),
    }
}

/// The display name of a module's area, from its .are.
pub fn module_title(data: &GameData, module: &str) -> String {
    let files = ModuleFiles::open(&data.root, module);
    let Some(area) = files.area_name() else { return module.to_string() };
    files
        .read(&area, crate::formats::erf::RES_TYPE_ARE)
        .and_then(|d| Gff::read(&d).ok())
        .map(|g| loc_name(data, &g.root, "Name"))
        .filter(|n| !n.trim().is_empty())
        .unwrap_or_else(|| module.to_string())
}

/// The game's map picture for an area: lbl_map + the area's name, or without the planet
/// prefix as KotOR 1 names them (ebo_m12aa: lbl_mapm12aa).
fn picture(data: &GameData, area: &str) -> Option<crate::formats::tga::Image> {
    let short = area.split_once('_').map(|(_, r)| r.to_string()).unwrap_or_else(|| area.to_string());
    for name in [format!("lbl_map{}", area), format!("lbl_map{}", short)] {
        if let Some((bytes, tpc)) = data.texture(&name) {
            let img = if tpc { crate::formats::tpc::decode(&bytes) } else { crate::formats::tga::decode(&bytes) };
            if img.is_some() {
                return img;
            }
        }
    }
    None
}

impl Area {
    /// Builds the map of `module`, with the objects of `git` (the save's copy of the area).
    pub fn build(data: &GameData, module: &str, git: &Struct, name_of: &dyn Fn(&Struct) -> String) -> Area {
        let files = ModuleFiles::open(&data.root, module);
        let area = files.area_name().unwrap_or_else(|| module.to_string());
        let are = files.read(&area, crate::formats::erf::RES_TYPE_ARE).and_then(|d| Gff::read(&d).ok());
        let calibration = are.as_ref().and_then(|a| Calibration::from_are(&a.root));
        let name = are.as_ref().map(|a| loc_name(data, &a.root, "Name")).filter(|n| !n.trim().is_empty()).unwrap_or_else(|| module.to_string());
        let sm = data.table("surfacemat");
        let walk = |m: u32| sm.int(m as usize, "walk") == Some(1);
        let mut floor = Floor::default();
        let lyt = files
            .read(&area, 3000)
            .or_else(|| data.resource(&area, "lyt", 3000))
            .map(|b| String::from_utf8_lossy(&b).to_string())
            .unwrap_or_default();
        let mut in_rooms = false;
        for line in lyt.lines() {
            let t = line.trim();
            if t.starts_with("roomcount") {
                in_rooms = true;
                continue;
            }
            if in_rooms {
                let parts: Vec<&str> = t.split_whitespace().collect();
                if parts.len() != 4 || parts[0].ends_with("count") {
                    in_rooms = parts.len() == 4;
                    if !in_rooms {
                        continue;
                    }
                }
                if let Some(wok) = files.read(parts[0], 2016).or_else(|| data.resource(parts[0], "wok", 2016)) {
                    floor.add_bwm(&wok, &walk);
                }
            }
        }
        let mut objects = Vec::new();
        let pos3 = |s: &Struct, a: &str, b: &str, c: &str| [s.float(a).unwrap_or(0.0), s.float(b).unwrap_or(0.0), s.float(c).unwrap_or(0.0)];
        if let Some(l) = git.list("Door List") {
            for (i, d) in l.iter().enumerate() {
                let pos = pos3(d, "X", "Y", "Z");
                let bearing = d.float("Bearing").unwrap_or(0.0);
                let leads = d.string("LinkedToModule").unwrap_or_default();
                let mut n = loc_name(data, d, "LocName");
                if n.is_empty() {
                    n = name_of(d);
                }
                objects.push(Object {
                    kind: if leads.is_empty() { Kind::Door } else { Kind::Exit },
                    list: "Door List",
                    index: i,
                    name: n,
                    tag: d.string("Tag").unwrap_or_default(),
                    pos,
                    facing: bearing,
                    leads_to: leads.to_ascii_lowercase(),
                    locked: d.int("Locked") == Some(1),
                    spots: door_sides(&floor, pos, bearing),
                    portrait: None,
                });
            }
        }
        if let Some(l) = git.list("TriggerList") {
            for (i, t) in l.iter().enumerate() {
                let leads = t.string("LinkedToModule").unwrap_or_default();
                if leads.is_empty() {
                    continue;
                }
                let pos = pos3(t, "XPosition", "YPosition", "ZPosition");
                // The trigger's shape is relative to its position; stand at its middle.
                let pts: Vec<(f32, f32)> = t
                    .list("Geometry")
                    .map(|g| g.iter().map(|p| (p.float("PointX").unwrap_or(0.0), p.float("PointY").unwrap_or(0.0))).collect())
                    .unwrap_or_default();
                let mid = if pts.is_empty() {
                    pos
                } else {
                    let n = pts.len() as f32;
                    [pos[0] + pts.iter().map(|p| p.0).sum::<f32>() / n, pos[1] + pts.iter().map(|p| p.1).sum::<f32>() / n, pos[2]]
                };
                let spot = floor.nearest(mid[0], mid[1], mid[2], 4.0);
                objects.push(Object {
                    kind: Kind::Exit,
                    list: "TriggerList",
                    index: i,
                    name: loc_name(data, t, "LocalizedName"),
                    tag: t.string("Tag").unwrap_or_default(),
                    pos: mid,
                    facing: 0.0,
                    leads_to: leads.to_ascii_lowercase(),
                    locked: false,
                    spots: spot.into_iter().collect(),
                    portrait: None,
                });
            }
        }
        if let Some(l) = git.list("Placeable List") {
            for (i, p) in l.iter().enumerate() {
                let useable = p.int("Useable") == Some(1);
                let container = p.int("HasInventory") == Some(1);
                if !useable && !container {
                    continue;
                }
                let pos = pos3(p, "X", "Y", "Z");
                let facing = p.float("Bearing").unwrap_or(0.0);
                let mut n = loc_name(data, p, "LocName");
                if n.is_empty() {
                    n = name_of(p);
                }
                objects.push(Object {
                    kind: if container { Kind::Container } else { Kind::Placeable },
                    list: "Placeable List",
                    index: i,
                    name: n,
                    tag: p.string("Tag").unwrap_or_default(),
                    pos,
                    facing,
                    leads_to: String::new(),
                    locked: p.int("Locked") == Some(1),
                    spots: spot_by(&floor, pos, facing, 1.1).into_iter().collect(),
                    portrait: None,
                });
            }
        }
        if let Some(l) = git.list("Creature List") {
            for (i, c) in l.iter().enumerate() {
                let pos = pos3(c, "XPosition", "YPosition", "ZPosition");
                let facing = c.float("YOrientation").unwrap_or(0.0).atan2(c.float("XOrientation").unwrap_or(1.0));
                let talks = c.string("Conversation").map_or(false, |s| !s.is_empty());
                objects.push(Object {
                    kind: Kind::Creature,
                    list: "Creature List",
                    index: i,
                    name: name_of(c),
                    tag: c.string("Tag").unwrap_or_default(),
                    pos,
                    facing,
                    leads_to: String::new(),
                    locked: false,
                    spots: if talks { spot_by(&floor, pos, facing, 1.3).into_iter().collect() } else { Vec::new() },
                    portrait: c.int("PortraitId").filter(|&p| p > 0),
                });
            }
        }
        if let Some(l) = git.list("WaypointList") {
            for (i, w) in l.iter().enumerate() {
                if w.int("MapNote") != Some(1) {
                    continue;
                }
                let pos = pos3(w, "XPosition", "YPosition", "ZPosition");
                objects.push(Object {
                    kind: Kind::Note,
                    list: "WaypointList",
                    index: i,
                    name: loc_name(data, w, "MapNote"),
                    tag: w.string("Tag").unwrap_or_default(),
                    pos,
                    facing: 0.0,
                    leads_to: String::new(),
                    locked: false,
                    spots: floor.nearest(pos[0], pos[1], pos[2], 3.0).into_iter().collect(),
                    portrait: None,
                });
            }
        }
        let picture = picture(data, &area);
        Area { module: module.to_string(), area, name, calibration, picture, floor, objects }
    }

    pub fn to_map(&self, x: f32, y: f32) -> Option<(f32, f32)> {
        self.calibration.as_ref().map(|c| c.to_map(x, y))
    }
}
