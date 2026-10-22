//! The installed game's own data, read only: its tables and strings, with mods in
//! Override taking precedence as they do in the game (KotOR 2 also reads Override's
//! subfolders). Every name the editor shows comes from here, never from a list of its own.

use crate::formats::erf::{ErfIndex, RES_TYPE_2DA};
use crate::formats::gff::{Gff, LocString};
use crate::formats::tables::{find_case_insensitive, Key, Tlk, TwoDa};
use crate::games::Game;
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

pub struct GameData {
    pub game: Game,
    pub root: PathBuf,
    key: Option<Key>,
    tlk: Option<Tlk>,
    overrides: HashMap<String, PathBuf>,
    tables: Mutex<HashMap<String, Arc<TwoDa>>>,
    gui_textures: Mutex<Option<Arc<ErfIndex>>>,
}

fn collect_overrides(dir: &Path, recurse: bool, out: &mut HashMap<String, PathBuf>) {
    let Ok(entries) = fs::read_dir(dir) else { return };
    let mut subdirs = Vec::new();
    for e in entries.filter_map(|e| e.ok()) {
        let path = e.path();
        if path.is_dir() {
            if recurse {
                subdirs.push(path);
            }
        } else {
            out.entry(e.file_name().to_string_lossy().to_ascii_lowercase()).or_insert(path);
        }
    }
    // Files directly in Override win over those in its subfolders.
    for d in subdirs {
        collect_overrides(&d, recurse, out);
    }
}

impl GameData {
    pub fn open(game: Game, root: &Path) -> GameData {
        let mut overrides = HashMap::new();
        if let Some(dir) = find_case_insensitive(root, "override") {
            collect_overrides(&dir, game == Game::K2, &mut overrides);
        }
        // KotOR 2's Steam Workshop mods load beside Override:
        // <library>/steamapps/workshop/content/208580/<item>/.
        if game == Game::K2 {
            let workshop = root
                .parent()
                .and_then(|common| common.parent())
                .map(|steamapps| steamapps.join("workshop").join("content").join("208580"));
            if let Some(dir) = workshop.filter(|d| d.is_dir()) {
                collect_overrides(&dir, true, &mut overrides);
            }
        }
        GameData {
            game,
            root: root.to_path_buf(),
            key: Key::open(root),
            tlk: find_case_insensitive(root, "dialog.tlk").and_then(|p| Tlk::open(&p)),
            overrides,
            tables: Mutex::new(HashMap::new()),
            gui_textures: Mutex::new(None),
        }
    }

    pub fn is_usable(&self) -> bool {
        self.key.is_some() && self.tlk.is_some()
    }

    /// A resource by name and extension: Override first, then the game's archives.
    pub fn resource(&self, name: &str, ext: &str, kind: u16) -> Option<Vec<u8>> {
        let file = format!("{}.{}", name.to_ascii_lowercase(), ext);
        if let Some(path) = self.overrides.get(&file) {
            if let Ok(data) = fs::read(path) {
                return Some(data);
            }
        }
        self.key.as_ref()?.read(name, kind)
    }

    /// Names of every resource of a type, from the archives and Override.
    pub fn resource_names(&self, ext: &str, kind: u16) -> Vec<String> {
        let mut names = self.key.as_ref().map(|k| k.names(kind)).unwrap_or_default();
        let suffix = format!(".{}", ext);
        for file in self.overrides.keys() {
            if let Some(stem) = file.strip_suffix(&suffix) {
                names.push(stem.to_string());
            }
        }
        names.sort();
        names.dedup();
        names
    }

    pub fn table(&self, name: &str) -> Arc<TwoDa> {
        let mut tables = self.tables.lock().unwrap();
        if let Some(t) = tables.get(name) {
            return t.clone();
        }
        let table = self
            .resource(name, "2da", RES_TYPE_2DA)
            .and_then(|d| TwoDa::read(&d).ok())
            .unwrap_or_default();
        let table = Arc::new(table);
        tables.insert(name.to_string(), table.clone());
        table
    }

    pub fn string(&self, strref: u32) -> Option<String> {
        if strref == u32::MAX {
            return None;
        }
        self.tlk.as_ref()?.get(strref).map(|t| crate::text::strip_codes(&t))
    }

    /// A localized string as the game shows it: its own text if it has any, else the
    /// string table's.
    pub fn loc(&self, loc: &LocString) -> String {
        if let Some((_, text)) = loc.strings.iter().find(|(id, t)| id / 2 == 0 && !t.is_empty()) {
            return crate::text::strip_codes(&crate::text::decode(text));
        }
        if let Some((_, text)) = loc.strings.iter().find(|(_, t)| !t.is_empty()) {
            return crate::text::strip_codes(&crate::text::decode(text));
        }
        self.string(loc.strref).unwrap_or_default()
    }

    /// A row's name: the string its `name` column points at, else its label.
    pub fn row_name(&self, table: &str, row: usize) -> Option<String> {
        let t = self.table(table);
        if let Some(name) = t.int(row, "name").and_then(|r| self.string(r as u32)) {
            if !name.trim().is_empty() && name != "Bad StrRef" {
                return Some(name);
            }
        }
        t.cell(row, "label").map(|s| s.replace('_', " "))
    }

    pub fn row_description(&self, table: &str, row: usize, column: &str) -> Option<String> {
        self.table(table).int(row, column).and_then(|r| self.string(r as u32))
    }

    pub fn gff(&self, name: &str, ext: &str, kind: u16) -> Option<Gff> {
        Gff::read(&self.resource(name, ext, kind)?).ok()
    }

    /// The GUI texture pack, where the portraits are (TexturePacks/swpc_tex_gui.erf).
    pub fn gui_textures(&self) -> Option<Arc<ErfIndex>> {
        let mut slot = self.gui_textures.lock().unwrap();
        if slot.is_none() {
            let path = find_case_insensitive(&self.root, "TexturePacks/swpc_tex_gui.erf")?;
            *slot = Some(Arc::new(ErfIndex::open(&path)?));
        }
        slot.clone()
    }

    /// A texture by name, as TPC or TGA bytes: Override, then the GUI pack, then the
    /// archives.
    pub fn texture(&self, name: &str) -> Option<(Vec<u8>, bool)> {
        let lower = name.to_ascii_lowercase();
        for (ext, tpc) in [("tpc", true), ("tga", false)] {
            if let Some(path) = self.overrides.get(&format!("{}.{}", lower, ext)) {
                if let Ok(d) = fs::read(path) {
                    return Some((d, tpc));
                }
            }
        }
        if let Some(pack) = self.gui_textures() {
            if let Some(data) = pack.read(&lower, crate::formats::erf::RES_TYPE_TPC) {
                return Some((data, true));
            }
        }
        let key = self.key.as_ref()?;
        if let Some(d) = key.read(&lower, crate::formats::erf::RES_TYPE_TPC) {
            return Some((d, true));
        }
        key.read(&lower, crate::formats::erf::RES_TYPE_TGA).map(|d| (d, false))
    }
}
