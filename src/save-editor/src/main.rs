//! KMRP Save Editor: the window and everything it does. The save itself is read, changed
//! and written by the library (lib.rs); this file turns it into what the screens show
//! (ui/state.slint) and answers the screens' actions.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

slint::include_modules!();

use kse_core::area;
use kse_core::catalog::{self, Catalog, ItemTemplate};
use kse_core::creature;
use kse_core::formats::erf::RES_TYPE_UTI;
use kse_core::formats::gff::{Struct, Value};
use kse_core::formats::{tga, tpc};
use kse_core::gamedata::GameData;
use kse_core::games::{self, Game, Install, SaveFolder, SaveKind};
use kse_core::globals::{self, Global, GlobalValue, Kind};
use kse_core::save::{self, Save, Summary, Who};
use slint::{Image, Model, ModelRc, Rgba8Pixel, SharedPixelBuffer, SharedString, VecModel};
use std::cell::RefCell;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::rc::Rc;
use std::sync::{Arc, Mutex};

fn model<T: Clone + 'static>(rows: Vec<T>) -> ModelRc<T> {
    ModelRc::new(VecModel::from(rows))
}

fn image(img: &tga::Image) -> Image {
    let buffer = SharedPixelBuffer::<Rgba8Pixel>::clone_from_slice(&img.rgba, img.width, img.height);
    Image::from_rgba8(buffer)
}

fn s(text: impl AsRef<str>) -> SharedString {
    SharedString::from(text.as_ref())
}

fn thousands(n: i64) -> String {
    let digits = n.abs().to_string();
    let mut out = String::new();
    for (i, c) in digits.chars().enumerate() {
        if i > 0 && (digits.len() - i) % 3 == 0 {
            out.push(',');
        }
        out.push(c);
    }
    if n < 0 {
        format!("-{}", out)
    } else {
        out
    }
}

fn played(seconds: i64) -> String {
    format!("{}h {:02}m", seconds / 3600, seconds % 3600 / 60)
}

const MONTHS: [&str; 12] = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/// A file's time as "22 Oct 2026, 01:23", in local time where the platform says what that
/// is (TZ offset is not available without a time zone database, so UTC elsewhere).
fn when(t: Option<std::time::SystemTime>) -> String {
    let Some(t) = t else { return String::new() };
    let secs = t.duration_since(std::time::UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0) + local_offset();
    let (y, m, d) = save::civil(secs.div_euclid(86_400));
    let r = secs.rem_euclid(86_400);
    format!("{} {} {}, {:02}:{:02}", d, MONTHS[(m - 1) as usize], y, r / 3600, r % 3600 / 60)
}

#[cfg(windows)]
fn local_offset() -> i64 {
    #[repr(C)]
    struct TimeZoneInformation {
        bias: i32,
        standard_name: [u16; 32],
        standard_date: [u16; 8],
        standard_bias: i32,
        daylight_name: [u16; 32],
        daylight_date: [u16; 8],
        daylight_bias: i32,
    }
    extern "system" {
        fn GetTimeZoneInformation(info: *mut TimeZoneInformation) -> u32;
    }
    let mut info: TimeZoneInformation = unsafe { std::mem::zeroed() };
    let mode = unsafe { GetTimeZoneInformation(&mut info) };
    let bias = info.bias + if mode == 2 { info.daylight_bias } else { info.standard_bias };
    -(bias as i64) * 60
}

#[cfg(not(windows))]
fn local_offset() -> i64 {
    // `date +%z` gives "+0200"; read once.
    thread_local!(static OFFSET: i64 = std::process::Command::new("date")
        .arg("+%z")
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .and_then(|t| {
            let t = t.trim();
            let sign = if t.starts_with('-') { -1 } else { 1 };
            let digits: String = t.chars().filter(|c| c.is_ascii_digit()).collect();
            let v: i64 = digits.parse().ok()?;
            Some(sign * (v / 100 * 3600 + v % 100 * 60))
        })
        .unwrap_or(0));
    OFFSET.with(|o| *o)
}

fn open_path(path: &Path) {
    let program = if cfg!(windows) {
        "explorer"
    } else if cfg!(target_os = "macos") {
        "open"
    } else {
        "xdg-open"
    };
    let _ = std::process::Command::new(program).arg(path).spawn();
}

/// Whether the game is running, so a save is not changed under it.
fn game_running(game: Game) -> bool {
    let names: &[&str] = match game {
        Game::K1 => &["swkotor.exe", "KOTOR", "swkotor"],
        Game::K2 => &["swkotor2.exe", "KOTOR2", "swkotor2"],
    };
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        // CREATE_NO_WINDOW: no console flashes up.
        let out = std::process::Command::new("tasklist")
            .args(["/FI", &format!("IMAGENAME eq {}", names[0]), "/NH"])
            .creation_flags(0x0800_0000)
            .output();
        return out.map_or(false, |o| String::from_utf8_lossy(&o.stdout).to_ascii_lowercase().contains(names[0]));
    }
    #[cfg(not(windows))]
    {
        return names[1..].iter().any(|n| {
            std::process::Command::new("pgrep").args(["-x", n]).output().map_or(false, |o| o.status.success())
        });
    }
}

// ---- settings, kept beside the backups ----

#[derive(Default)]
struct Settings {
    added: Vec<PathBuf>,
    /// The install to use for each game, when the player picked one.
    k1_dir: Option<PathBuf>,
    k2_dir: Option<PathBuf>,
    k2: bool,
    light: bool,
}

impl Settings {
    fn path() -> PathBuf {
        games::data_dir().join("settings.txt")
    }

    fn load() -> Settings {
        let mut s = Settings::default();
        if let Ok(text) = std::fs::read_to_string(Self::path()) {
            for line in text.lines() {
                if let Some(p) = line.strip_prefix("added=") {
                    s.added.push(PathBuf::from(p));
                } else if let Some(p) = line.strip_prefix("k1dir=") {
                    s.k1_dir = Some(PathBuf::from(p));
                } else if let Some(p) = line.strip_prefix("k2dir=") {
                    s.k2_dir = Some(PathBuf::from(p));
                } else if line == "game=k2" {
                    s.k2 = true;
                } else if line == "theme=light" {
                    s.light = true;
                }
            }
        }
        s
    }

    fn store(&self) {
        let mut text = String::new();
        for a in &self.added {
            text.push_str(&format!("added={}\n", a.display()));
        }
        for (key, dir) in [("k1dir", &self.k1_dir), ("k2dir", &self.k2_dir)] {
            if let Some(d) = dir {
                text.push_str(&format!("{}={}\n", key, d.display()));
            }
        }
        text.push_str(if self.k2 { "game=k2\n" } else { "game=k1\n" });
        text.push_str(if self.light { "theme=light\n" } else { "theme=dark\n" });
        let _ = std::fs::create_dir_all(games::data_dir());
        let _ = std::fs::write(Self::path(), text);
    }
}

/// Where a picked item or save goes.
#[derive(Clone, Copy, PartialEq)]
enum Target {
    None,
    Inventory,
    Container,
    Class,
    Compare,
    ImportNpc(usize),
}

/// A game's tables, names and (when asked) item list. Made in the background at start
/// for the game not on screen, so switching to it is instant.
fn build_game(game: Game, path: &Path, with_items: bool) -> Game_ {
    let data = Arc::new(GameData::open(game, path));
    let catalog = Arc::new(Catalog::build(&data));
    let items = with_items.then(|| Arc::new(catalog::item_templates(&data)));
    Game_ { data, catalog, items }
}

struct Game_ {
    data: Arc<GameData>,
    catalog: Arc<Catalog>,
    items: Option<Arc<Vec<ItemTemplate>>>,
}

struct State {
    settings: Settings,
    installs: Vec<Install>,
    game: Game,
    games: HashMap<Game, Game_>,
    ready: Arc<Mutex<HashMap<Game, Game_>>>,
    ready_items: Arc<Mutex<HashMap<Game, Arc<Vec<ItemTemplate>>>>>,
    picker_tab: usize,
    inventory_tab: usize,
    saves: Vec<(SaveFolder, Summary)>,
    shots: Arc<Mutex<HashMap<PathBuf, Option<Arc<tga::Image>>>>>,
    portraits: HashMap<String, Option<Image>>,
    selected: usize,
    save: Option<Save>,
    original: Option<Save>,
    read_only: bool,
    whos: Vec<Who>,
    who: usize,
    tab: i32,
    story: i32,
    feat_query: String,
    power_query: String,
    picker_query: String,
    picker_ids: Vec<usize>,
    target: Target,
    other_saves: Vec<SaveFolder>,
    compare: Option<(String, Vec<Global>)>,
    global_filter: (String, bool),
    selected_box: Option<(&'static str, usize)>,
    status: (String, bool),
}

type Shared = Rc<RefCell<State>>;

impl State {
    fn current(&self) -> Option<&Game_> {
        self.games.get(&self.game)
    }

    fn data(&self) -> Option<Arc<GameData>> {
        self.current().map(|g| g.data.clone())
    }

    fn catalog(&self) -> Option<Arc<Catalog>> {
        self.current().map(|g| g.catalog.clone())
    }

    fn ensure_game(&mut self, game: Game) {
        if self.games.contains_key(&game) {
            return;
        }
        if let Some(ready) = self.ready.lock().unwrap().remove(&game) {
            self.games.insert(game, ready);
            return;
        }
        if let Some(install) = self.installs.iter().find(|i| i.game == game) {
            self.games.insert(game, build_game(game, &install.path, false));
        }
    }

    fn portrait(&mut self, resref: &str) -> Option<Image> {
        let key = resref.to_ascii_lowercase();
        if key.is_empty() {
            return None;
        }
        if let Some(p) = self.portraits.get(&key) {
            return p.clone();
        }
        let img = self.data().and_then(|d| d.texture(&key)).and_then(|(bytes, is_tpc)| {
            if is_tpc {
                tpc::decode(&bytes)
            } else {
                tga::decode(&bytes)
            }
        });
        let img = img.map(|i| image(&i));
        self.portraits.insert(key, img.clone());
        img
    }

    /// An icon texture, or the fallback when the game has no such texture.
    fn icon(&mut self, name: &str, fallback: &str) -> Option<Image> {
        self.portrait(name).or_else(|| self.portrait(fallback))
    }

    fn item_icon(&mut self, item: &Struct) -> Option<Image> {
        let base = self.data()?.table("baseitems");
        let row = item.int("BaseItem").unwrap_or(0) as usize;
        let (name, fallback) = catalog::item_icon(&base, row, item.int("ModelVariation").unwrap_or(1));
        self.icon(&name, &fallback)
    }

    fn portrait_of(&mut self, c: &Struct) -> Option<Image> {
        let id = c.int("PortraitId")?;
        let resref = self.data()?.table("portraits").cell(id as usize, "baseresref")?.to_string();
        self.portrait(&resref)
    }

    fn creature_name(&self, who: Who) -> String {
        let Some(save) = self.save.as_ref() else { return String::new() };
        let Some(c) = save.creature(who) else { return String::new() };
        let mut name = creature::name(c);
        if name.is_empty() {
            if let (Some(Value::LocString(l)), Some(d)) = (c.get("FirstName"), self.data()) {
                name = d.loc(l);
            }
        }
        if name.is_empty() {
            if let (Who::Npc(i), Some(cat)) = (who, self.catalog()) {
                name = cat.npc_names.get(i).cloned().unwrap_or_default();
            }
        }
        name
    }

    fn npc_name(&self, index: usize) -> String {
        if self.save.as_ref().map_or(false, |s| s.creature(Who::Npc(index)).is_some()) {
            let n = self.creature_name(Who::Npc(index));
            if !n.is_empty() {
                return n;
            }
        }
        self.catalog().and_then(|c| c.npc_names.get(index).cloned()).unwrap_or_else(|| format!("Member {}", index + 1))
    }

    fn who(&self) -> Who {
        self.whos.get(self.who).copied().unwrap_or(Who::Player)
    }

    fn item_templates(&mut self) -> Arc<Vec<ItemTemplate>> {
        let game = self.game;
        if let Some(g) = self.games.get_mut(&game) {
            if g.items.is_none() {
                let ready = self.ready_items.lock().unwrap().remove(&game);
                g.items = Some(ready.unwrap_or_else(|| Arc::new(catalog::item_templates(&g.data))));
            }
            return g.items.clone().unwrap();
        }
        Arc::new(Vec::new())
    }

    fn item_name(&self, item: &Struct) -> String {
        let Some(data) = self.data() else { return String::new() };
        let name = match item.get("LocalizedName") {
            Some(Value::LocString(l)) => data.loc(l),
            _ => String::new(),
        };
        if name.trim().is_empty() {
            item.string("Tag").unwrap_or_default()
        } else {
            name.replace('\n', " ")
        }
    }

    fn item_kind(&self, item: &Struct) -> (String, i64) {
        let Some(data) = self.data() else { return (String::new(), 1) };
        let base = item.int("BaseItem").unwrap_or(0) as usize;
        let t = data.table("baseitems");
        let kind = t.int(base, "name").and_then(|r| data.string(r as u32)).unwrap_or_default();
        (kind, t.int(base, "stacking").unwrap_or(1).max(1))
    }
}

/// Every install found, with the one the player picked for each game first.
fn installs_for(settings: &Settings) -> Vec<Install> {
    let mut extra = settings.added.clone();
    extra.extend(settings.k1_dir.iter().cloned());
    extra.extend(settings.k2_dir.iter().cloned());
    let mut installs = games::find_installs(&extra);
    let picked = |i: &Install| {
        let want = match i.game {
            Game::K1 => &settings.k1_dir,
            Game::K2 => &settings.k2_dir,
        };
        want.as_ref().map_or(false, |w| games::clean(w) == i.path)
    };
    installs.sort_by_key(|i| !picked(i));
    installs
}

// ---- filling the screens ----

fn fill_saves(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let theme = ui.global::<Theme>();
    theme.set_k2(st.game == Game::K2);
    app.set_has_k1(st.installs.iter().any(|i| i.game == Game::K1));
    app.set_has_k2(st.installs.iter().any(|i| i.game == Game::K2));
    app.set_showing_k2(st.game == Game::K2);
    st.ensure_game(st.game);
    app.set_game_folder(s(st
        .installs
        .iter()
        .find(|i| i.game == st.game)
        .map(|i| format!("{}: {}", i.source, i.path.display()))
        .unwrap_or_default()));

    let folders = games::find_saves(&st.installs, st.game, &st.settings.added);
    let mut saves: Vec<(SaveFolder, Summary)> =
        folders.into_iter().filter_map(|f| save::summary(&f.path).map(|s| (f, s))).collect();
    saves.sort_by(|a, b| b.1.modified.cmp(&a.1.modified));
    st.saves = saves;
    let shots = st.shots.lock().unwrap().clone();
    let rows: Vec<SaveRow> = st
        .saves
        .iter()
        .map(|(f, sm)| {
            let shot = shots.get(&f.path).cloned().flatten();
            SaveRow {
                name: s(&sm.name),
                area: s(&sm.area),
                time: s(played(sm.seconds)),
                date: s(when(sm.modified)),
                tag: s(match f.kind {
                    SaveKind::Cloud => "CLOUD",
                    SaveKind::Added => "ADDED",
                    SaveKind::Local => "",
                }),
                has_shot: shot.is_some(),
                shot: shot.map(|i| image(&i)).unwrap_or_default(),
            }
        })
        .collect();
    app.set_saves(model(rows));
    let n = st.saves.len();
    app.set_saves_note(s(match n {
        0 => String::new(),
        1 => "1 save found".to_string(),
        _ => format!("{} saves found", n),
    }));
    let installed = st.installs.iter().any(|i| i.game == st.game);
    if !installed && st.installs.is_empty() {
        app.set_empty_title(s("No KotOR game found"));
        app.set_empty_note(s(
            "The editor looks in every Steam library, GOG and disc install. If the game is somewhere else, use Add a Save Folder below and pick the game's folder or a saves folder.",
        ));
    } else {
        app.set_empty_title(s(format!("No {} saves found", st.game.title())));
        app.set_empty_note(s(
            "Saves made in the game appear here. Saves kept somewhere else (copied from a phone, a Switch or another PC) can be added with Add a Save Folder below.",
        ));
    }
    if st.selected >= n {
        st.selected = 0;
    }
    app.set_selected_save(st.selected as i32);
    fill_preview(ui, st);
    load_shots(ui, st);
}

/// Decodes the save pictures away from the window and puts each in its row as it comes.
fn load_shots(ui: &AppWindow, st: &State) {
    let paths: Vec<PathBuf> = st.saves.iter().map(|(f, _)| f.path.clone()).collect();
    let cache = st.shots.clone();
    let weak = ui.as_weak();
    std::thread::spawn(move || {
        for (i, path) in paths.into_iter().enumerate() {
            if cache.lock().unwrap().contains_key(&path) {
                continue;
            }
            let img = save::screenshot(&path).map(Arc::new);
            cache.lock().unwrap().insert(path.clone(), img.clone());
            let Some(img) = img else { continue };
            let weak = weak.clone();
            let _ = slint::invoke_from_event_loop(move || {
                let Some(ui) = weak.upgrade() else { return };
                let app = ui.global::<App>();
                let rows = app.get_saves();
                if let Some(mut row) = rows.row_data(i) {
                    row.shot = image(&img);
                    row.has_shot = true;
                    rows.set_row_data(i, row);
                }
                if app.get_selected_save() as usize == i && app.get_page() == 0 {
                    app.set_preview_shot(image(&img));
                    app.set_preview_has_shot(true);
                }
            });
        }
    });
}

fn is_xbox_save(path: &Path) -> bool {
    std::fs::read_dir(path).map_or(false, |d| {
        d.filter_map(|e| e.ok()).any(|e| {
            let n = e.file_name().to_string_lossy().to_ascii_lowercase();
            n == "savemeta.xbx" || n == "saveimage.xbx"
        })
    })
}

fn fill_preview(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let Some((folder, sm)) = st.saves.get(st.selected).cloned() else { return };
    app.set_preview_name(s(&sm.name));
    app.set_preview_area(s(&sm.area));
    app.set_preview_time(s(played(sm.seconds)));
    app.set_preview_date(s(when(sm.modified)));
    app.set_preview_tag(s(if folder.kind == SaveKind::Cloud { "Steam Cloud" } else { "" }));
    let shot = st.shots.lock().unwrap().get(&folder.path).cloned().flatten();
    app.set_preview_has_shot(shot.is_some());
    app.set_preview_shot(shot.map(|i| image(&i)).unwrap_or_default());
    let party: Vec<Image> = sm.portraits.iter().filter_map(|p| st.portrait(p)).collect();
    app.set_preview_party(model(party));
    let mut pc = sm.pc_name.clone();
    if pc.is_empty() {
        // KotOR 1 keeps the name only in the player creature.
        pc = Save::open(&folder.path).ok().and_then(|sv| sv.player().map(creature::name)).unwrap_or_default();
    }
    app.set_preview_pc(s(pc));
    let xbox = is_xbox_save(&folder.path);
    app.set_preview_read_only(xbox);
    app.set_preview_warning(s(if xbox {
        "An original Xbox save. The Xbox checks a signature on every save, so this one can be looked at but not changed."
    } else if folder.kind == SaveKind::Cloud {
        "A Steam Cloud save. Close the game and let Steam finish syncing before changing it; Steam sends the changed save to the cloud the next time the game starts."
    } else {
        ""
    }));
}

fn open_selected(ui: &AppWindow, st: &mut State) {
    let Some((folder, _)) = st.saves.get(st.selected).cloned() else { return };
    st.ensure_game(folder.game);
    match (Save::open(&folder.path), Save::open(&folder.path)) {
        (Ok(sv), Ok(orig)) => {
            st.read_only = is_xbox_save(&folder.path);
            st.save = Some(sv);
            st.original = Some(orig);
            st.who = 0;
            st.tab = 0;
            st.story = 0;
            st.compare = None;
            st.selected_box = None;
            st.status = (String::new(), false);
            st.global_filter = (String::new(), false);
            ui.global::<App>().set_page(1);
            fill_editor(ui, st);
        }
        (Err(e), _) | (_, Err(e)) => message(ui, "This save could not be opened", &e),
    }
}

fn message(ui: &AppWindow, title: &str, body: &str) {
    let app = ui.global::<App>();
    app.set_message_title(s(title));
    app.set_message_body(s(body));
    app.set_overlay(4);
}

fn fill_editor(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let mut whos = vec![Who::Player];
    whos.extend(save.npcs().into_iter().map(Who::Npc));
    st.whos = whos.clone();
    if st.who >= whos.len() {
        st.who = 0;
    }
    let nfo = &save.nfo.root;
    app.set_context_line(s(format!(
        "{} · {} · {}",
        save::summary(&save.folder).map(|x| x.name).unwrap_or_default(),
        nfo.string("AREANAME").unwrap_or_default(),
        save.game.title()
    )));
    let backups = games::data_dir().join("backups").join(save.game.title()).join(
        save.folder.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default(),
    );
    app.set_backup_path(s(backups.display().to_string()));

    let cat = st.catalog();
    let mut members = Vec::new();
    for w in whos.clone() {
        let name = st.creature_name(w);
        let c = st.save.as_ref().unwrap().creature(w).cloned();
        let sub = match w {
            Who::Player => format!("Player · level {}", c.as_ref().map(creature::level).unwrap_or(0)),
            Who::Npc(i) => {
                let sv = st.save.as_ref().unwrap();
                if sv.in_party(i) {
                    "In the party".to_string()
                } else if sv.recruited(i) {
                    format!("Recruited · level {}", c.as_ref().map(creature::level).unwrap_or(0))
                } else {
                    "Not recruited".to_string()
                }
            }
        };
        let portrait = c.as_ref().and_then(|c| st.portrait_of(c));
        let prefix = format!("{:?}.", w);
        let changed = st.save.as_ref().map_or(false, |sv| sv.changes.iter().any(|c| c.starts_with(&prefix)));
        members.push(Member {
            changed,
            name: s(if name.is_empty() { "Player".to_string() } else { name }),
            sub: s(sub),
            has_portrait: portrait.is_some(),
            portrait: portrait.unwrap_or_default(),
        });
    }
    app.set_members(model(members));
    app.set_who(st.who as i32);
    app.set_tab(st.tab);
    app.set_is_player(st.who() == Who::Player);
    let _ = cat;
    fill_character(ui, st);
    fill_abilities(ui, st);
    fill_inventory(ui, st);
    fill_party(ui, st);
    fill_story(ui, st);
    fill_bar(ui, st);
}

/// Which tab holds each change, for the orange marks beside the tab names.
fn tab_of(change: &str) -> usize {
    let field = change.rsplit_once('.').map(|(_, f)| f).unwrap_or(change);
    if change.starts_with("Player.") || change.starts_with("Npc(") {
        if field.starts_with("skill") || field.starts_with("feat") || field.starts_with("power") {
            1
        } else if field == "position" {
            4
        } else {
            0
        }
    } else if change.starts_with("inventory.") || change.contains("PT_GOLD") || change.contains("PT_ITEM_") {
        2
    } else if change.starts_with("npc") || change.contains("PT_AVAIL_NPCS") || change.contains("PT_INFLUENCE") || change.contains("PT_XP_POOL") {
        3
    } else {
        4
    }
}

fn fill_bar(ui: &AppWindow, st: &State) {
    let app = ui.global::<App>();
    let mut tabs = vec![false; 5];
    if let Some(sv) = st.save.as_ref() {
        for c in &sv.changes {
            tabs[tab_of(c)] = true;
        }
    }
    app.set_tab_changed(model(tabs));
    app.set_change_count(st.save.as_ref().map_or(0, |s| s.changes.len() as i32));
    app.set_status(s(&st.status.0));
    app.set_status_bad(st.status.1);
}

fn fill_character(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let who = st.who();
    let Some(c) = st.save.as_ref().and_then(|s| s.creature(who)).cloned() else { return };
    let o = st.original.as_ref().and_then(|s| s.creature(who)).cloned().unwrap_or_else(|| c.clone());
    let Some(cat) = st.catalog() else { return };

    app.set_name(s(creature::name(&c)));
    app.set_name_changed(creature::name(&c) != creature::name(&o));
    let classes: Vec<String> =
        creature::classes(&c).iter().map(|(id, lv)| format!("{} {}", cat.class_name(*id), lv)).collect();
    app.set_classes(s(classes.join(" · ")));
    app.set_can_add_class(creature::classes(&c).len() < 2);
    let xp = creature::experience(&c);
    app.set_xp(xp as i32);
    app.set_xp_changed(xp != creature::experience(&o));
    let level = creature::level(&c);
    let max = cat.max_level();
    let next = cat.xp_for(level + 1);
    let note = match next {
        Some(need) if level < max && xp >= need => format!(
            "Level {}. This is enough XP for level {}: the game offers the level-up itself, with its own choices of skills, feats and powers.",
            level,
            cat.level_for(xp).min(max)
        ),
        Some(need) if level < max => format!(
            "Level {}. Level {} needs {} XP. Give more XP and the game offers the level-up itself, with its own choices of skills, feats and powers.",
            level,
            level + 1,
            thousands(need)
        ),
        _ => format!("Level {}, the highest the game allows.", level),
    };
    app.set_level_note(s(note));
    app.set_max_xp(cat.xp_for(max).unwrap_or(0) as i32);
    app.set_max_level(s(max.to_string()));
    app.set_alignment(creature::alignment(&c) as i32);
    app.set_alignment_changed(creature::alignment(&c) != creature::alignment(&o));

    const NAMES: [(&str, &str); 6] = [
        ("Strength", "Melee hits and damage"),
        ("Dexterity", "Defence, ranged hits"),
        ("Constitution", "Health"),
        ("Intelligence", "Skill points"),
        ("Wisdom", "Force, power saves"),
        ("Charisma", "Force, persuasion"),
    ];
    let attrs: Vec<Stat> = creature::ATTRIBUTES
        .iter()
        .zip(NAMES)
        .map(|(label, (name, note))| {
            let v = creature::attribute(&c, label);
            let m = creature::modifier(v);
            Stat {
                label: s(name),
                note: s(note),
                value: v as i32,
                minimum: 1,
                maximum: 100,
                r#mod: s(if m >= 0 { format!("+{}", m) } else { m.to_string() }),
                changed: v != creature::attribute(&o, label),
                ..Default::default()
            }
        })
        .collect();
    app.set_attributes(model(attrs));

    let (hp, hp_max) = creature::health(&c);
    let (fp, fp_max) = creature::force(&c);
    app.set_health(s(format!("{} / {}", hp, hp_max)));
    app.set_force(s(format!("{} / {}", fp, fp_max)));
    app.set_health_note(s(format!("Base {} + Constitution", c.int("HitPoints").unwrap_or(0))));
    app.set_force_note(s(if fp_max > 0 {
        format!("Base {} + Wisdom, Charisma", c.int("ForcePoints").unwrap_or(0))
    } else {
        "No Force class".to_string()
    }));

    let portrait = st.portrait_of(&c);
    app.set_has_portrait(portrait.is_some());
    app.set_portrait(portrait.unwrap_or_default());
    let female = c.int("Gender") == Some(1);
    app.set_look_note(s(format!(
        "{}, portrait {}, body {}. A new portrait brings the body that goes with it.",
        if female { "Female" } else { "Male" },
        c.int("PortraitId").unwrap_or(0),
        c.int("Appearance_Type").unwrap_or(0)
    )));
    app.set_look_changed(c.int("PortraitId") != o.int("PortraitId"));
    let p = area::position(&c);
    let po = area::position(&o);
    app.set_position_x(s(format!("{:.2}", p[0])));
    app.set_position_y(s(format!("{:.2}", p[1])));
    app.set_position_z(s(format!("{:.2}", p[2])));
    app.set_position_changed(p != po);
}

fn row(id: i64, name: impl AsRef<str>, note: impl AsRef<str>) -> Named {
    Named { id: id as i32, name: s(name), note: s(note), ..Default::default() }
}

fn named(rows: impl Iterator<Item = (i64, String, String)>) -> ModelRc<Named> {
    model(rows.map(|(id, name, note)| row(id, name, note)).collect())
}

/// Every entry of a catalogue list, under its group's heading, with its icon: what the
/// creature has is lit. Entries it has that the game's list lacks (a removed mod) come
/// last, so they can still be removed.
fn ability_rows(st: &mut State, list: &[kse_core::catalog::Entry], have: &[i64], before: &[i64], query: &str, fallback_name: &str) -> Vec<Named> {
    let q = query.trim().to_lowercase();
    let mut out = Vec::new();
    let mut group = String::new();
    for e in list {
        if !q.is_empty() && !e.name.to_lowercase().contains(&q) {
            continue;
        }
        if e.group != group {
            group = e.group.clone();
            out.push(Named { header: true, ..row(-1, group.to_uppercase(), "") });
        }
        let owned = have.contains(&e.id);
        let icon = st.portrait(&e.icon);
        out.push(Named {
            owned,
            changed: owned != before.contains(&e.id),
            has_icon: icon.is_some(),
            icon: icon.unwrap_or_default(),
            ..row(e.id, &e.name, short(&e.description))
        });
    }
    let unknown: Vec<i64> = have.iter().copied().filter(|id| !list.iter().any(|e| e.id == *id)).collect();
    if !unknown.is_empty() && q.is_empty() {
        out.push(Named { header: true, ..row(-1, "NOT IN THE GAME'S LIST", "") });
        for id in unknown {
            out.push(Named { owned: true, ..row(id, format!("{} {}", fallback_name, id), "From a mod that is no longer installed, or hidden") });
        }
    }
    out
}

fn short(text: &str) -> String {
    let first = text.split(['\n', '.']).next().unwrap_or("").trim();
    if first.chars().count() > 90 {
        format!("{}…", first.chars().take(88).collect::<String>())
    } else {
        first.to_string()
    }
}

fn fill_abilities(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let who = st.who();
    let Some(c) = st.save.as_ref().and_then(|s| s.creature(who)).cloned() else { return };
    let o = st.original.as_ref().and_then(|s| s.creature(who)).cloned().unwrap_or_else(|| c.clone());
    let Some(cat) = st.catalog() else { return };
    let skill_icons: Vec<Option<Image>> = cat.skills.iter().map(|sk| st.portrait(&sk.icon)).collect();
    let skills: Vec<Stat> = cat
        .skills
        .iter()
        .enumerate()
        .map(|(i, sk)| {
            let v = creature::skill(&c, i);
            let icon = skill_icons[i].clone();
            Stat {
                has_icon: icon.is_some(),
                icon: icon.unwrap_or_default(),
                label: s(&sk.name),
                note: s(""),
                value: v as i32,
                minimum: 0,
                maximum: 99,
                r#mod: s(""),
                changed: v != creature::skill(&o, i),
            }
        })
        .collect();
    app.set_skills(model(skills));
    let (feats_now, feats_before) = (creature::feats(&c), creature::feats(&o));
    let (powers_now, powers_before) = (creature::powers(&c), creature::powers(&o));
    let (fq, pq) = (st.feat_query.clone(), st.power_query.clone());
    let feat_rows = ability_rows(st, &cat.feats, &feats_now, &feats_before, &fq, "Feat");
    let power_rows = ability_rows(st, &cat.powers, &powers_now, &powers_before, &pq, "Power");
    app.set_feats(model(feat_rows));
    app.set_powers(model(power_rows));
    app.set_feat_count(feats_now.len() as i32);
    app.set_power_count(powers_now.len() as i32);
    let force = |id: i64| cat.is_force_class(id);
    let can = creature::can_have_powers(&c, &force);
    app.set_can_powers(can);
    let jedi: Vec<String> = creature::classes(&c)
        .iter()
        .filter(|(id, _)| cat.is_force_class(*id))
        .map(|(id, _)| cat.class_name(*id))
        .collect();
    app.set_power_note(s(jedi.join(", ")));
}

fn item_rows(st: &mut State, items: &[Struct], original: &[Struct]) -> Vec<ItemRow> {
    items
        .iter()
        .enumerate()
        .map(|(i, it)| {
            let icon = st.item_icon(it);
            let (kind, max) = st.item_kind(it);
            let stack = it.int("StackSize").unwrap_or(1);
            let changed = original.get(i).map_or(true, |o| o != it);
            ItemRow {
                index: i as i32,
                name: s(st.item_name(it)),
                kind: s(kind),
                stack: stack as i32,
                max_stack: max.max(stack) as i32,
                tag: s(it.string("Tag").unwrap_or_default()),
                changed,
                has_icon: icon.is_some(),
                icon: icon.unwrap_or_default(),
            }
        })
        .collect()
}

fn fill_inventory(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let orig = st.original.as_ref();
    let get = |s: &Save, l: &str| s.party_int(l).unwrap_or(0);
    let credits = get(save, "PT_GOLD");
    app.set_credits(credits as i32);
    app.set_credits_changed(orig.map_or(false, |o| get(o, "PT_GOLD") != credits));
    let crafting = save.party_int("PT_ITEM_COMPONEN").is_some();
    app.set_has_crafting(crafting);
    let comp = get(save, "PT_ITEM_COMPONEN");
    let chem = get(save, "PT_ITEM_CHEMICAL");
    app.set_components(comp as i32);
    app.set_chemicals(chem as i32);
    app.set_components_changed(orig.map_or(false, |o| get(o, "PT_ITEM_COMPONEN") != comp));
    app.set_chemicals_changed(orig.map_or(false, |o| get(o, "PT_ITEM_CHEMICAL") != chem));
    let items = save.inventory();
    let original = orig.map(|o| o.inventory()).unwrap_or_default();
    let base = st.data().map(|d| d.table("baseitems"));
    let tab = st.inventory_tab;
    let shown = |it: &Struct| {
        tab == 0
            || base.as_ref().map_or(true, |b| catalog::item_category(b, it.int("BaseItem").unwrap_or(0) as usize).unwrap_or(7) == tab)
    };
    let rows: Vec<ItemRow> = item_rows(st, &items, &original).into_iter().filter(|r| shown(&items[r.index as usize])).collect();
    app.set_inventory_tab(tab as i32);
    app.set_picker_tabs(model(catalog::ITEM_CATEGORIES.iter().map(|c| s(c)).collect()));
    app.set_picker_tabs_a(model(catalog::ITEM_CATEGORIES[..4].iter().map(|c| s(c)).collect()));
    app.set_picker_tabs_b(model(catalog::ITEM_CATEGORIES[4..].iter().map(|c| s(c)).collect()));
    app.set_items(model(rows));
    app.set_inventory_note(s("A stack can be as large as the game allows for that kind of item."));
}

fn fill_party(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let count = save.npc_count();
    let mut rows = Vec::new();
    for i in 0..count {
        let sv = st.save.as_ref().unwrap();
        let has = sv.creature(Who::Npc(i)).is_some();
        let influence = sv.influence(i);
        let changed = st.original.as_ref().map_or(false, |o| {
            o.recruited(i) != sv.recruited(i) || o.selectable(i) != sv.selectable(i) || o.influence(i) != influence
        }) || sv.changes.iter().any(|c| c.starts_with(&format!("npc{}.", i)));
        let (recruited, selectable, in_party) = (sv.recruited(i), sv.selectable(i), sv.in_party(i));
        let portrait = sv.creature(Who::Npc(i)).cloned().and_then(|c| st.portrait_of(&c));
        rows.push(NpcRow {
            index: i as i32,
            name: s(st.npc_name(i)),
            has_portrait: portrait.is_some(),
            portrait: portrait.unwrap_or_default(),
            has_creature: has,
            recruited,
            selectable,
            in_party,
            influence: influence.unwrap_or(0).max(0) as i32,
            has_influence: influence.map_or(false, |v| v >= 0),
            changed,
        });
    }
    app.set_npcs(model(rows));
    let sv = st.save.as_ref().unwrap();
    let xp = sv.party_int("PT_XP_POOL").unwrap_or(0);
    app.set_party_xp(xp as i32);
    app.set_party_xp_changed(st.original.as_ref().map_or(false, |o| o.party_int("PT_XP_POOL").unwrap_or(0) != xp));
}

fn fill_story(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    app.set_story_section(st.story);
    fill_globals(ui, st);
    fill_area(ui, st);
    fill_more(ui, st);
}

fn fill_globals(ui: &AppWindow, st: &State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let Some(g) = save.globals.as_ref() else {
        app.set_variables(model(Vec::new()));
        app.set_globals_note(s("This save has no global variables file."));
        return;
    };
    let all = globals::list(&g.root);
    let orig = st.original.as_ref().and_then(|o| o.globals.as_ref()).map(|g| globals::list(&g.root)).unwrap_or_default();
    let other = st.compare.as_ref().map(|(_, l)| l);
    let (query, only) = (&st.global_filter.0, st.global_filter.1);
    let mut rows = Vec::new();
    for (pos, v) in all.iter().enumerate() {
        let changed = orig.get(pos).map_or(false, |o| o.value != v.value);
        let theirs = other.and_then(|l| l.iter().find(|o| o.kind == v.kind && o.name == v.name));
        let differs = theirs.map_or(false, |t| t.value != v.value);
        if only && !(if other.is_some() { differs } else { changed }) {
            continue;
        }
        if !query.trim().is_empty() && !v.name.to_lowercase().contains(&query.trim().to_lowercase()) {
            continue;
        }
        if rows.len() >= 200 {
            break;
        }
        let (on, number, text) = match &v.value {
            GlobalValue::Bool(b) => (*b, 0, String::new()),
            GlobalValue::Number(n) => (false, *n as i32, String::new()),
            GlobalValue::Text(t) => (false, 0, t.clone()),
        };
        rows.push(GlobalRow {
            index: pos as i32,
            name: s(&v.name),
            kind: match v.kind {
                Kind::Boolean => 0,
                Kind::Number => 1,
                Kind::String => 2,
            },
            on,
            number,
            text: s(text),
            changed,
            other: s(theirs.map(|t| if t.value != v.value { format!("theirs: {}", t.value.display()) } else { "same".into() }).unwrap_or_default()),
        });
    }
    let shown = rows.len();
    app.set_variables(model(rows));
    let total = all.len();
    app.set_compare_name(s(st.compare.as_ref().map(|c| c.0.clone()).unwrap_or_default()));
    let mut note = format!(
        "{} switches, {} numbers and {} texts that the game's scripts read. {} shown.",
        all.iter().filter(|g| g.kind == Kind::Boolean).count(),
        all.iter().filter(|g| g.kind == Kind::Number).count(),
        all.iter().filter(|g| g.kind == Kind::String).count(),
        if shown >= 200 && shown < total { "The first 200".to_string() } else { shown.to_string() }
    );
    if let Some((name, _)) = &st.compare {
        note.push_str(&format!(" Compared with {}.", name));
    }
    app.set_globals_note(s(note));
}

fn fill_area(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let Some(git) = save.area_git().map(|g| g.root.clone()) else {
        app.set_doors(model(Vec::new()));
        app.set_boxes(model(Vec::new()));
        app.set_area_note(s("The area of this save could not be read."));
        return;
    };
    let orig_doors = st.original.as_ref().and_then(|o| o.area_git()).map(|g| area::doors(&g.root)).unwrap_or_default();
    let doors: Vec<DoorRow> = area::doors(&git)
        .into_iter()
        .map(|d| {
            let o = orig_doors.get(d.index);
            let mut note = Vec::new();
            if d.key_required {
                note.push(format!("needs the key {}", d.key));
            } else if d.locked {
                note.push(format!("Security {}", d.lock_dc));
            }
            if d.plot {
                note.push("story door".into());
            }
            DoorRow {
                index: d.index as i32,
                tag: s(if d.tag.is_empty() { format!("Door {}", d.index + 1) } else { d.tag.clone() }),
                note: s(note.join(", ")),
                locked: d.locked,
                open: d.open,
                changed: o.map_or(false, |o| o.locked != d.locked || o.open != d.open),
            }
        })
        .collect();
    app.set_doors(model(doors));
    let data = st.data();
    let namer = |p: &Struct| -> String {
        let n = match (p.get("LocName"), &data) {
            (Some(Value::LocString(l)), Some(d)) => d.loc(l),
            _ => String::new(),
        };
        if n.trim().is_empty() {
            p.string("Tag").unwrap_or_default()
        } else {
            n
        }
    };
    let boxes = area::containers(&git, &namer);
    let rows: Vec<BoxRow> = boxes
        .iter()
        .enumerate()
        .map(|(_, b)| BoxRow {
            index: b.index as i32,
            name: s(&b.name),
            note: s(format!(
                "{}{} item{}{}",
                if b.list == area::STORES { "store, " } else { "" },
                b.items,
                if b.items == 1 { "" } else { "s" },
                if b.locked { ", locked" } else { "" }
            )),
        })
        .collect();
    app.set_boxes(model(rows));
    let selected = st.selected_box.and_then(|(l, i)| boxes.iter().position(|b| b.list == l && b.index == i));
    app.set_selected_box(selected.map_or(-1, |p| p as i32));
    let items: Vec<Struct> = st
        .selected_box
        .and_then(|(l, i)| area::container(&git, l, i))
        .and_then(|c| c.list("ItemList").cloned())
        .unwrap_or_default();
    let orig_items: Vec<Struct> = st
        .selected_box
        .and_then(|(l, i)| st.original.as_ref().and_then(|o| o.area_git()).and_then(|g| area::container(&g.root, l, i).cloned()))
        .and_then(|c| c.list("ItemList").cloned())
        .unwrap_or_default();
    let module = save.nfo.root.string("AREANAME").unwrap_or_default();
    let item_rows = item_rows(st, &items, &orig_items);
    app.set_box_items(model(item_rows));
    app.set_area_note(s(format!(
        "{}: what the game finds when the save loads. Story scripts may lock a door again.",
        module
    )));
}

fn fill_more(ui: &AppWindow, st: &mut State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let data = st.data();
    let map = save.party.root.child("GlxyMap");
    let orig_map = st.original.as_ref().and_then(|o| o.party.root.child("GlxyMap").cloned());
    let count = map.and_then(|m| m.int("GlxyMapNumPnts")).unwrap_or(0).min(16);
    let mask = map.and_then(|m| m.int("GlxyMapPlntMsk")).unwrap_or(0);
    let omask = orig_map.as_ref().and_then(|m| m.int("GlxyMapPlntMsk")).unwrap_or(mask);
    let mut planets = Vec::new();
    for i in 0..count {
        let name = data
            .as_ref()
            .and_then(|d| d.row_name("planetary", i as usize))
            .unwrap_or_else(|| format!("Planet {}", i + 1));
        if name.starts_with("Live Planet") {
            continue;
        }
        let on = mask & (1 << i) != 0;
        planets.push(Toggle { index: i as i32, name: s(name), on, value: 0, changed: on != (omask & (1 << i) != 0) });
    }
    app.set_planets(model(planets));
    let cards = save.party.root.list("PT_PAZAAKCARDS").cloned().unwrap_or_default();
    let ocards = st.original.as_ref().and_then(|o| o.party.root.list("PT_PAZAAKCARDS").cloned()).unwrap_or_default();
    let pazaak: Vec<Toggle> = cards
        .iter()
        .enumerate()
        .map(|(i, c)| {
            let v = c.int("PT_PAZAAKCOUNT").unwrap_or(0);
            Toggle {
                index: i as i32,
                name: s(format!("Side card {}", i + 1)),
                on: v > 0,
                value: v as i32,
                changed: ocards.get(i).and_then(|o| o.int("PT_PAZAAKCOUNT")) != Some(v),
            }
        })
        .collect();
    app.set_pazaak(model(pazaak));
    let cheat = save.party.root.int("PT_CHEAT_USED").unwrap_or(0) != 0 || save.nfo.root.int("CHEATUSED").unwrap_or(0) != 0;
    let ocheat = st
        .original
        .as_ref()
        .map_or(cheat, |o| o.party.root.int("PT_CHEAT_USED").unwrap_or(0) != 0 || o.nfo.root.int("CHEATUSED").unwrap_or(0) != 0);
    app.set_cheat_used(cheat);
    app.set_cheat_changed(cheat != ocheat);
    let name = save.nfo.root.string("SAVEGAMENAME").unwrap_or_default();
    app.set_save_name(s(&name));
    app.set_save_name_changed(st.original.as_ref().map_or(false, |o| o.nfo.root.string("SAVEGAMENAME").unwrap_or_default() != name));
    fill_journal(ui, st);
}

/// The journal as the game shows it: each quest's name and its current entry, from the
/// game's global.jrl.
fn fill_journal(ui: &AppWindow, st: &State) {
    let app = ui.global::<App>();
    let Some(save) = st.save.as_ref() else { return };
    let data = st.data();
    let jrl = data.as_ref().and_then(|d| d.gff("global", "jrl", 2056));
    let entries = save.party.root.list("JNL_Entries").cloned().unwrap_or_default();
    let loc = |s: &Struct, label: &str| -> String {
        match (s.get(label), &data) {
            (Some(Value::LocString(l)), Some(d)) => d.loc(l),
            _ => String::new(),
        }
    };
    let rows: Vec<(i64, String, String)> = entries
        .iter()
        .enumerate()
        .map(|(i, e)| {
            let tag = e.string("JNL_PlotID").unwrap_or_default();
            let state = e.int("JNL_State").unwrap_or(0);
            let category = jrl
                .as_ref()
                .and_then(|j| j.root.list("Categories"))
                .and_then(|l| l.iter().find(|c| c.string("Tag").map_or(false, |t| t.eq_ignore_ascii_case(&tag))));
            let name = category.map(|c| loc(c, "Name")).filter(|n| !n.trim().is_empty()).unwrap_or_else(|| tag.clone());
            let text = category
                .and_then(|c| c.list("EntryList"))
                .and_then(|l| l.iter().find(|x| x.int("ID") == Some(state)))
                .map(|x| loc(x, "Text"))
                .unwrap_or_default();
            (i as i64, name, short(&text))
        })
        .collect();
    app.set_journal(named(rows.into_iter()));
    app.set_journal_note(s("Removing an entry only hides it; the story switches stay as they are."));
}

// ---- actions ----

fn with<F: Fn(&AppWindow, &mut State) + 'static>(ui: &AppWindow, state: &Shared, f: F) -> impl Fn() + 'static {
    let weak = ui.as_weak();
    let state = state.clone();
    move || {
        if let Some(ui) = weak.upgrade() {
            f(&ui, &mut state.borrow_mut());
        }
    }
}

macro_rules! on {
    ($ui:expr, $state:expr, $name:ident, |$u:ident, $st:ident $(, $arg:ident : $ty:ty)*| $body:block) => {{
        let weak = $ui.as_weak();
        let state = $state.clone();
        $ui.global::<App>().$name(move |$($arg: $ty),*| {
            if let Some($u) = weak.upgrade() {
                let $st = &mut *state.borrow_mut();
                $body
            }
        });
    }};
}

fn edit_who(ui: &AppWindow, st: &mut State, key: &str, f: impl Fn(&mut Struct)) {
    let who = st.who();
    if let Some(save) = st.save.as_mut() {
        save.edit(who, key, f);
    }
    st.status = (String::new(), false);
    refresh_after_edit(ui, st);
}

fn refresh_after_edit(ui: &AppWindow, st: &mut State) {
    match st.tab {
        0 => fill_character(ui, st),
        1 => fill_abilities(ui, st),
        2 => fill_inventory(ui, st),
        3 => fill_party(ui, st),
        _ => fill_story(ui, st),
    }
    fill_bar(ui, st);
}

fn open_items_picker(ui: &AppWindow, st: &mut State, target: Target, title: &str) {
    st.target = target;
    st.picker_query.clear();
    let app = ui.global::<App>();
    app.set_overlay_title(s(title));
    app.set_overlay_note(s(
        "Every item the game has, mods included. Type to narrow the list; click an item to add one.",
    ));
    app.set_overlay(1);
    st.picker_tab = 0;
    app.set_picker_tab(0);
    app.set_picker_tabs(model(catalog::ITEM_CATEGORIES.iter().map(|c| s(c)).collect()));
    let _ = st.item_templates();
    search_items(ui, st);
}

fn search_items(ui: &AppWindow, st: &mut State) {
    let templates = st.item_templates();
    let q = st.picker_query.trim().to_lowercase();
    let mut ids = Vec::new();
    let mut rows = Vec::new();
    let tab = st.picker_tab;
    for (i, t) in templates.iter().enumerate() {
        if tab != 0 && t.category != tab {
            continue;
        }
        if !q.is_empty() && !t.name.to_lowercase().contains(&q) && !t.resref.contains(&q) && !t.kind.to_lowercase().contains(&q) {
            continue;
        }
        ids.push(i);
        let base = st.data().map(|d| d.table("baseitems"));
        let fallback = base.as_ref().map(|b| catalog::item_icon(b, t.base_item as usize, 1).1).unwrap_or_default();
        let icon = st.icon(&t.icon, &fallback);
        rows.push(Named {
            has_icon: icon.is_some(),
            icon: icon.unwrap_or_default(),
            ..row(i as i64, &t.name, format!("{} · {}", t.kind, t.resref))
        });
        if rows.len() >= 200 {
            break;
        }
    }
    st.picker_ids = ids;
    ui.global::<App>().set_picker(model(rows));
}

fn new_item(st: &mut State, index: usize, like: Option<&Struct>) -> Option<Struct> {
    let templates = st.item_templates();
    let t = templates.get(index)?;
    let data = st.data()?;
    let g = data.gff(&t.resref, "uti", RES_TYPE_UTI)?;
    Some(catalog::item_from_template(&g.root, like, 1))
}

fn open_save_picker(ui: &AppWindow, st: &mut State, target: Target, title: &str, note: &str) {
    let current = st.save.as_ref().map(|s| s.folder.clone());
    let npc = if let Target::ImportNpc(i) = target { Some(i) } else { None };
    let mut others: Vec<SaveFolder> = st
        .saves
        .iter()
        .map(|(f, _)| f.clone())
        .filter(|f| Some(&f.path) != current.as_ref())
        .collect();
    if let Some(i) = npc {
        others.retain(|f| {
            std::fs::read_dir(&f.path).is_ok()
                && Save::open(&f.path).map_or(false, |sv| sv.creature(Who::Npc(i)).is_some())
        });
    }
    let shots = st.shots.lock().unwrap().clone();
    let rows: Vec<SaveRow> = others
        .iter()
        .filter_map(|f| {
            let sm = save::summary(&f.path)?;
            let shot = shots.get(&f.path).cloned().flatten();
            Some(SaveRow {
                name: s(sm.name),
                area: s(sm.area),
                time: s(played(sm.seconds)),
                date: s(when(sm.modified)),
                tag: s(""),
                has_shot: shot.is_some(),
                shot: shot.map(|i| image(&i)).unwrap_or_default(),
            })
        })
        .collect();
    st.other_saves = others;
    st.target = target;
    let app = ui.global::<App>();
    app.set_other_saves(model(rows));
    app.set_overlay_title(s(title));
    app.set_overlay_note(s(if st.other_saves.is_empty() { "No other save of this game has what is needed." } else { note }));
    app.set_overlay(3);
}

fn main() {
    let ui = AppWindow::new().expect("the window could not be made");
    let settings = Settings::load();
    let installs = installs_for(&settings);
    let k2_only = installs.iter().all(|i| i.game == Game::K2) && !installs.is_empty();
    let k1_only = installs.iter().all(|i| i.game == Game::K1) && !installs.is_empty();
    let game = if k2_only || (settings.k2 && !k1_only) { Game::K2 } else { Game::K1 };
    ui.global::<Theme>().set_dark(!settings.light);
    let state: Shared = Rc::new(RefCell::new(State {
        settings,
        installs,
        game,
        games: HashMap::new(),
        ready: Arc::new(Mutex::new(HashMap::new())),
        ready_items: Arc::new(Mutex::new(HashMap::new())),
        picker_tab: 0,
        inventory_tab: 0,
        saves: Vec::new(),
        shots: Arc::new(Mutex::new(HashMap::new())),
        portraits: HashMap::new(),
        selected: 0,
        save: None,
        original: None,
        read_only: false,
        whos: Vec::new(),
        who: 0,
        tab: 0,
        story: 0,
        feat_query: String::new(),
        power_query: String::new(),
        picker_query: String::new(),
        picker_ids: Vec::new(),
        target: Target::None,
        other_saves: Vec::new(),
        compare: None,
        global_filter: (String::new(), false),
        selected_box: None,
        status: (String::new(), false),
    }));
    fill_saves(&ui, &mut state.borrow_mut());
    {
        // The other game's data and both games' item lists, made while the player looks
        // at the list; the first switch and the first Add an Item then cost nothing.
        let st = state.borrow();
        let (ready, ready_items, current) = (st.ready.clone(), st.ready_items.clone(), st.game);
        let jobs: Vec<(Game, PathBuf)> = [Game::K1, Game::K2]
            .iter()
            .filter_map(|g| st.installs.iter().find(|i| i.game == *g).map(|i| (*g, i.path.clone())))
            .collect();
        std::thread::spawn(move || {
            for (game, path) in jobs {
                if game == current {
                    let data = GameData::open(game, &path);
                    ready_items.lock().unwrap().insert(game, Arc::new(catalog::item_templates(&data)));
                } else {
                    let built = build_game(game, &path, true);
                    ready.lock().unwrap().insert(game, built);
                }
            }
        });
    }

    // ---- the save list ----
    on!(ui, state, on_switch_game, |u, st, k2: bool| {
        st.game = if k2 { Game::K2 } else { Game::K1 };
        st.settings.k2 = k2;
        st.selected = 0;
        st.portraits.clear();
        fill_saves(&u, st);
    });
    on!(ui, state, on_select_save, |u, st, i: i32| {
        st.selected = i.max(0) as usize;
        u.global::<App>().set_selected_save(i);
        fill_preview(&u, st);
    });
    on!(ui, state, on_open_save, |u, st| { open_selected(&u, st); });
    on!(ui, state, on_show_folder, |_u, st| {
        if let Some((f, _)) = st.saves.get(st.selected) {
            open_path(&f.path);
        }
    });
    on!(ui, state, on_open_saves_folder, |_u, st| {
        let folder = st.saves.get(st.selected).and_then(|(f, _)| f.path.parent().map(|p| p.to_path_buf())).or_else(|| {
            st.installs.iter().find(|i| i.game == st.game).map(|i| i.path.clone())
        });
        if let Some(f) = folder {
            open_path(&f);
        }
    });
    on!(ui, state, on_add_save_folder, |u, st| {
        if let Some(folder) = rfd::FileDialog::new().set_title("Pick a save, a saves folder or a game folder").pick_folder() {
            if !st.settings.added.contains(&folder) {
                st.settings.added.push(folder.clone());
                st.settings.store();
            }
            st.installs = installs_for(&st.settings);
            if let Some(g) = games::identify(&folder).or_else(|| save::peek_game(&folder)) {
                st.game = g;
            }
            fill_saves(&u, st);
        }
    });

    on!(ui, state, on_choose_game_folder, |u, st| {
        let Some(folder) = rfd::FileDialog::new().set_title("Pick the game's folder (the one with chitin.key)").pick_folder() else { return };
        match games::identify(&folder) {
            Some(game) => {
                match game {
                    Game::K1 => st.settings.k1_dir = Some(folder),
                    Game::K2 => st.settings.k2_dir = Some(folder),
                }
                st.settings.store();
                st.installs = installs_for(&st.settings);
                st.games.remove(&game);
                st.ready.lock().unwrap().remove(&game);
                st.ready_items.lock().unwrap().remove(&game);
                st.portraits.clear();
                st.game = game;
                st.selected = 0;
                fill_saves(&u, st);
            }
            None => message(&u, "That is not a KotOR folder", "Pick the folder that holds chitin.key and the game's program."),
        }
    });

    // ---- the editor ----
    on!(ui, state, on_back, |u, st| {
        if st.save.as_ref().map_or(false, |s| !s.changes.is_empty()) {
            message(&u, "There are changes not saved", "Save them or press Revert first, so nothing is lost by accident.");
            return;
        }
        st.save = None;
        st.original = None;
        u.global::<App>().set_page(0);
        fill_saves(&u, st);
    });
    on!(ui, state, on_select_who, |u, st, i: i32| {
        st.who = i.max(0) as usize;
        st.feat_query.clear();
        st.power_query.clear();
        fill_editor(&u, st);
    });
    on!(ui, state, on_select_tab, |u, st, i: i32| {
        st.tab = i;
        u.global::<App>().set_tab(i);
        refresh_after_edit(&u, st);
    });

    // Character
    on!(ui, state, on_set_name, |u, st, text: SharedString| {
        if st.who() != Who::Player || text.trim().is_empty() {
            return;
        }
        let t = text.to_string();
        let who = st.who();
        if let Some(save) = st.save.as_mut() {
            save.edit(who, "name", |c| creature::set_name(c, &t));
            let bytes = kse_core::text::encode(&t);
            if save.party.root.get("PT_PCNAME").is_some() {
                save.edit_party_table("name", |p| p.set("PT_PCNAME", Value::String(bytes.clone())));
            }
        }
        fill_bar(&u, st);
        let app = u.global::<App>();
        app.set_name_changed(true);
    });
    on!(ui, state, on_set_xp, |u, st, xp: i32| {
        let xp = xp.max(0) as i64;
        edit_who(&u, st, "xp", |c| creature::set_experience(c, xp));
    });
    on!(ui, state, on_xp_to_next, |u, st| {
        let Some(cat) = st.catalog() else { return };
        let level = st.save.as_ref().and_then(|s| s.creature(st.who())).map(creature::level).unwrap_or(1);
        let current = st.save.as_ref().and_then(|s| s.creature(st.who())).map(creature::experience).unwrap_or(0);
        let mut target = cat.xp_for(level + 1).unwrap_or(current);
        if current >= target {
            target = cat.xp_for(cat.level_for(current) + 1).unwrap_or(current);
        }
        if target > current {
            edit_who(&u, st, "xp", |c| creature::set_experience(c, target));
        }
    });
    on!(ui, state, on_xp_to_max, |u, st| {
        let Some(cat) = st.catalog() else { return };
        if let Some(xp) = cat.xp_for(cat.max_level()) {
            edit_who(&u, st, "xp", |c| creature::set_experience(c, xp));
        }
    });
    on!(ui, state, on_set_alignment, |u, st, v: i32| {
        edit_who(&u, st, "alignment", |c| creature::set_alignment(c, v as i64));
    });
    on!(ui, state, on_set_attribute, |u, st, i: i32, v: i32| {
        let label = creature::ATTRIBUTES[i.clamp(0, 5) as usize];
        edit_who(&u, st, label, |c| creature::set_attribute(c, label, v as i64));
    });
    on!(ui, state, on_heal_all, |u, st| {
        let whos = st.whos.clone();
        if let Some(save) = st.save.as_mut() {
            for w in whos {
                save.edit(w, "heal", creature::heal);
            }
        }
        refresh_after_edit(&u, st);
        fill_editor(&u, st);
    });
    on!(ui, state, on_open_look, |u, st| {
        let Some(cat) = st.catalog() else { return };
        let current = st.save.as_ref().and_then(|s| s.creature(st.who())).and_then(|c| c.int("PortraitId")).unwrap_or(-1);
        let mut rows = Vec::new();
        for p in cat.portraits.clone() {
            if let Some(img) = st.portrait(&p.resref) {
                rows.push(PortraitRow { id: p.id as i32, image: img, female: p.female, current: p.id == current });
            }
        }
        let app = u.global::<App>();
        app.set_looks(model(rows));
        app.set_overlay_title(s("Change Look"));
        app.set_overlay_note(s(
            "The portraits character creation offers. The body that goes with the portrait comes too, in the same build as now.",
        ));
        app.set_overlay(2);
    });
    on!(ui, state, on_pick_look, |u, st, id: i32| {
        let Some(cat) = st.catalog() else { return };
        let Some(p) = cat.portrait_for(id as i64).cloned() else { return };
        let current_id = st.save.as_ref().and_then(|s| s.creature(st.who())).and_then(|c| c.int("PortraitId")).unwrap_or(-1);
        let current = cat.portrait_for(current_id).cloned();
        u.global::<App>().set_overlay(0);
        edit_who(&u, st, "look", |c| creature::set_look(c, &p, current.as_ref()));
        fill_editor(&u, st);
    });
    on!(ui, state, on_open_add_class, |u, st| {
        let Some(cat) = st.catalog() else { return };
        let Some(c) = st.save.as_ref().and_then(|s| s.creature(st.who())).cloned() else { return };
        let have: Vec<i64> = creature::classes(&c).iter().map(|(id, _)| *id).collect();
        let droid = have.iter().any(|id| cat.class(*id).map_or(false, |k| k.droid));
        let rows = cat
            .classes
            .iter()
            .filter(|k| !have.contains(&k.id) && k.droid == droid && !k.name.is_empty())
            .map(|k| {
                let note = if k.force_die > 0 {
                    format!("Jedi class: {} Health and {} Force a level", k.hit_die, k.force_die)
                } else {
                    format!("{} Health a level", k.hit_die)
                };
                (k.id, k.name.clone(), note)
            });
        st.target = Target::Class;
        let app = u.global::<App>();
        app.set_picker(named(rows));
        app.set_overlay_title(s("Add a Class"));
        app.set_overlay_note(s(
            "A second class at level 1, as a level-up into it would leave the character: its Health and Force are added and the XP is raised to the new level if needed. The game knows two classes at most.",
        ));
        app.set_overlay(5);
    });
    on!(ui, state, on_set_position, |u, st, x: SharedString, y: SharedString, z: SharedString| {
        let (Ok(x), Ok(y), Ok(z)) = (x.trim().parse::<f32>(), y.trim().parse::<f32>(), z.trim().parse::<f32>()) else {
            message(&u, "That is not a position", "Type three numbers, for example 12.5, -3 and 0.");
            return;
        };
        if st.who() == Who::Player {
            edit_who(&u, st, "position", |c| area::set_position(c, [x, y, z]));
        }
    });

    // Abilities
    on!(ui, state, on_set_skill, |u, st, i: i32, v: i32| {
        let i = i.max(0) as usize;
        edit_who(&u, st, &format!("skill{}", i), |c| creature::set_skill(c, i, v as i64));
    });
    on!(ui, state, on_search_feats, |u, st, q: SharedString| {
        st.feat_query = q.to_string();
        fill_abilities(&u, st);
    });
    on!(ui, state, on_search_powers, |u, st, q: SharedString| {
        st.power_query = q.to_string();
        fill_abilities(&u, st);
    });
    on!(ui, state, on_add_feat, |u, st, id: i32| {
        st.feat_query.clear();
        edit_who(&u, st, &format!("feat{}", id), |c| {
            creature::add_feat(c, id as i64);
        });
    });
    on!(ui, state, on_remove_feat, |u, st, id: i32| {
        edit_who(&u, st, &format!("feat{}", id), |c| {
            creature::remove_feat(c, id as i64);
        });
    });
    on!(ui, state, on_add_power, |u, st, id: i32| {
        st.power_query.clear();
        let Some(cat) = st.catalog() else { return };
        edit_who(&u, st, &format!("power{}", id), move |c| {
            creature::add_power(c, id as i64, &|k| cat.is_force_class(k));
        });
    });
    on!(ui, state, on_remove_power, |u, st, id: i32| {
        edit_who(&u, st, &format!("power{}", id), |c| {
            creature::remove_power(c, id as i64);
        });
    });

    // Inventory
    on!(ui, state, on_set_credits, |u, st, v: i32| {
        if let Some(save) = st.save.as_mut() {
            save.set_party_int("PT_GOLD", v.max(0) as i64);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_components, |u, st, v: i32| {
        if let Some(save) = st.save.as_mut() {
            save.set_party_int("PT_ITEM_COMPONEN", v.max(0) as i64);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_chemicals, |u, st, v: i32| {
        if let Some(save) = st.save.as_mut() {
            save.set_party_int("PT_ITEM_CHEMICAL", v.max(0) as i64);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_stack, |u, st, row: i32, v: i32| {
        let row = row.max(0) as usize;
        if let Some(save) = st.save.as_mut() {
            save.edit_inventory(&format!("stack{}", row), |items| {
                if let Some(it) = items.get_mut(row) {
                    it.set_int("StackSize", v.max(1) as i64, Value::Word(1));
                }
            });
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_remove_item, |u, st, row: i32| {
        let row = row.max(0) as usize;
        if let Some(save) = st.save.as_mut() {
            save.edit_inventory(&format!("remove{}", row), |items| {
                if row < items.len() {
                    items.remove(row);
                }
            });
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_select_inventory_tab, |u, st, i: i32| {
        st.inventory_tab = i.max(0) as usize;
        fill_inventory(&u, st);
    });
    on!(ui, state, on_open_add_item, |u, st| {
        open_items_picker(&u, st, Target::Inventory, "Add an Item");
    });

    // Party
    on!(ui, state, on_set_recruited, |u, st, i: i32, on: bool| {
        if let Some(save) = st.save.as_mut() {
            save.set_recruited(i.max(0) as usize, on);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_selectable, |u, st, i: i32, on: bool| {
        if let Some(save) = st.save.as_mut() {
            save.set_selectable(i.max(0) as usize, on);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_influence, |u, st, i: i32, v: i32| {
        if let Some(save) = st.save.as_mut() {
            save.set_influence(i.max(0) as usize, v as i64);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_party_xp, |u, st, v: i32| {
        if let Some(save) = st.save.as_mut() {
            save.set_party_int("PT_XP_POOL", v.max(0) as i64);
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_import_npc, |u, st, i: i32| {
        let name = st.npc_name(i.max(0) as usize);
        open_save_picker(
            &u,
            st,
            Target::ImportNpc(i.max(0) as usize),
            &format!("Bring {} from Another Save", name),
            &format!("{} comes over as they are in the save you pick: level, items worn, feats and powers. They are listed as recruited here.", name),
        );
    });

    // Story
    on!(ui, state, on_select_story, |u, st, i: i32| {
        st.story = i;
        fill_story(&u, st);
    });
    on!(ui, state, on_filter_globals, |u, st, q: SharedString, only: bool| {
        st.global_filter = (q.to_string(), only);
        fill_globals(&u, st);
    });
    on!(ui, state, on_set_global_bool, |u, st, index: i32, on: bool| {
        let index = index.max(0) as usize;
        if let Some(save) = st.save.as_mut() {
            let all = save.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default();
            if let Some(g) = all.get(index).cloned() {
                save.edit_globals(&format!("b{}", g.index), |root| globals::set(root, &g, &GlobalValue::Bool(on)));
            }
        }
        fill_globals(&u, st);
        fill_bar(&u, st);
    });
    on!(ui, state, on_set_global_number, |u, st, index: i32, v: i32| {
        let index = index.max(0) as usize;
        if let Some(save) = st.save.as_mut() {
            let all = save.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default();
            if let Some(g) = all.get(index).cloned() {
                save.edit_globals(&format!("n{}", g.index), |root| globals::set(root, &g, &GlobalValue::Number(v as i64)));
            }
        }
        fill_globals(&u, st);
        fill_bar(&u, st);
    });
    on!(ui, state, on_set_global_text, |u, st, index: i32, t: SharedString| {
        let index = index.max(0) as usize;
        if let Some(save) = st.save.as_mut() {
            let all = save.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default();
            if let Some(g) = all.get(index).cloned() {
                save.edit_globals(&format!("s{}", g.index), |root| globals::set(root, &g, &GlobalValue::Text(t.to_string())));
            }
        }
        fill_globals(&u, st);
        fill_bar(&u, st);
    });
    on!(ui, state, on_open_compare, |u, st| {
        open_save_picker(
            &u,
            st,
            Target::Compare,
            "Compare with Another Save",
            "Pick a save from before or after a quest. Every global variable that differs is marked, with the other save's value beside it.",
        );
    });
    on!(ui, state, on_use_other, |u, st, index: i32| {
        let index = index.max(0) as usize;
        let Some(theirs) = st.compare.as_ref().map(|c| c.1.clone()) else { return };
        if let Some(save) = st.save.as_mut() {
            let all = save.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default();
            if let Some(g) = all.get(index).cloned() {
                if let Some(t) = theirs.iter().find(|t| t.kind == g.kind && t.name == g.name) {
                    let v = t.value.clone();
                    save.edit_globals(&format!("{:?}{}", g.kind, g.index), |root| globals::set(root, &g, &v));
                }
            }
        }
        fill_globals(&u, st);
        fill_bar(&u, st);
    });
    on!(ui, state, on_use_all_other, |u, st| {
        let Some(theirs) = st.compare.as_ref().map(|c| c.1.clone()) else { return };
        if let Some(save) = st.save.as_mut() {
            let all = save.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default();
            for (g, v) in globals::compare(&all, &theirs) {
                save.edit_globals(&format!("{:?}{}", g.kind, g.index), |root| globals::set(root, &g, &v));
            }
        }
        fill_globals(&u, st);
        fill_bar(&u, st);
    });
    on!(ui, state, on_set_door_locked, |u, st, i: i32, on: bool| {
        if let Some(save) = st.save.as_mut() {
            save.edit_area(&format!("door{}", i), |git| area::set_door_locked(git, i.max(0) as usize, on));
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_door_open, |u, st, i: i32, on: bool| {
        if let Some(save) = st.save.as_mut() {
            save.edit_area(&format!("door{}", i), |git| area::set_door_open(git, i.max(0) as usize, on));
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_select_box, |u, st, row: i32| {
        let Some(save) = st.save.as_ref() else { return };
        let Some(git) = save.area_git() else { return };
        let boxes = area::containers(&git.root, &|p: &Struct| p.string("Tag").unwrap_or_default());
        st.selected_box = boxes.get(row.max(0) as usize).map(|b| (b.list, b.index));
        fill_area(&u, st);
    });
    on!(ui, state, on_remove_box_item, |u, st, row: i32| {
        let Some((list, index)) = st.selected_box else { return };
        if let Some(save) = st.save.as_mut() {
            save.edit_area(&format!("box{}{}", list, index), |git| {
                if let Some(items) = area::container_mut(git, list, index).and_then(|c| c.list_mut("ItemList")) {
                    let row = row.max(0) as usize;
                    if row < items.len() {
                        items.remove(row);
                    }
                    if list == area::STORES {
                        for (i, it) in items.iter_mut().enumerate() {
                            it.id = i as u32;
                        }
                    }
                }
            });
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_add_box_item, |u, st| {
        open_items_picker(&u, st, Target::Container, "Add an Item Here");
    });
    on!(ui, state, on_set_planet, |u, st, i: i32, on: bool| {
        if let Some(save) = st.save.as_mut() {
            save.edit_party_table(&format!("planet{}", i), |p| {
                if let Some(map) = p.child_mut("GlxyMap") {
                    let mask = map.int("GlxyMapPlntMsk").unwrap_or(0);
                    // The game keeps two 16-bit halves and sets a planet's bit in both
                    // (measured on real saves: Dantooine to Korriban and Yavin, 3..7 and
                    // 11, and the same again from 19).
                    let i = i.clamp(0, 15);
                    let bit = (1i64 << i) | (1i64 << (i + 16));
                    let mask = if on { mask | bit } else { mask & !bit };
                    map.set_int("GlxyMapPlntMsk", mask, Value::Dword(0));
                }
            });
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_cheat, |u, st, on: bool| {
        if let Some(save) = st.save.as_mut() {
            save.edit_party_table("cheat", |p| {
                p.set_int("PT_CHEAT_USED", on as i64, Value::Byte(0));
            });
            save.edit_nfo(|n| {
                n.set_int("CHEATUSED", on as i64, Value::Byte(0));
            });
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_pazaak, |u, st, i: i32, v: i32| {
        if let Some(save) = st.save.as_mut() {
            save.edit_party_table(&format!("pazaak{}", i), |p| {
                if let Some(card) = p.list_mut("PT_PAZAAKCARDS").and_then(|l| l.get_mut(i.max(0) as usize)) {
                    card.set_int("PT_PAZAAKCOUNT", v.clamp(0, 9) as i64, Value::Int(0));
                }
            });
        }
        refresh_after_edit(&u, st);
    });

    on!(ui, state, on_remove_journal, |u, st, i: i32| {
        if let Some(save) = st.save.as_mut() {
            save.edit_party_table(&format!("journal{}", i), |p| {
                if let Some(l) = p.list_mut("JNL_Entries") {
                    let i = i.max(0) as usize;
                    if i < l.len() {
                        l.remove(i);
                    }
                }
            });
        }
        refresh_after_edit(&u, st);
    });
    on!(ui, state, on_set_save_name, |u, st, t: SharedString| {
        if t.trim().is_empty() {
            return;
        }
        if let Some(save) = st.save.as_mut() {
            save.rename(t.trim());
        }
        refresh_after_edit(&u, st);
    });

    // ---- saving ----
    on!(ui, state, on_save_changes, |u, st| {
        let Some(game) = st.save.as_ref().map(|s| s.game) else { return };
        if st.read_only {
            message(&u, "This save cannot be changed", "It is an original Xbox save; the Xbox would call it damaged.");
            return;
        }
        if game_running(game) {
            message(
                &u,
                &format!("{} is running", game.title()),
                "Close the game first. A save changed while the game runs can be overwritten by it, or loaded half old and half new.",
            );
            return;
        }
        let backups = games::data_dir().join("backups");
        let result = st.save.as_mut().unwrap().write(&backups);
        match result {
            Ok(backup) => {
                let folder = st.save.as_ref().unwrap().folder.clone();
                st.original = Save::open(&folder).ok();
                if let Ok(fresh) = Save::open(&folder) {
                    st.save = Some(fresh);
                }
                st.shots.lock().unwrap().remove(&folder);
                st.status = (format!("Saved. The save as it was is kept in {}", backup.display()), false);
            }
            Err(e) => st.status = (format!("Nothing was changed: {}", e), true),
        }
        fill_editor(&u, st);
    });
    on!(ui, state, on_revert, |u, st| {
        if let Some(folder) = st.save.as_ref().map(|s| s.folder.clone()) {
            st.save = Save::open(&folder).ok();
            st.original = Save::open(&folder).ok();
            st.status = (String::new(), false);
            fill_editor(&u, st);
        }
    });
    on!(ui, state, on_open_backups, |_u, st| {
        let dir = games::data_dir().join("backups").join(st.game.title());
        let _ = std::fs::create_dir_all(&dir);
        open_path(&dir);
    });

    // ---- pop-ups ----
    on!(ui, state, on_close_overlay, |u, st| {
        st.target = Target::None;
        u.global::<App>().set_overlay(0);
    });
    on!(ui, state, on_select_picker_tab, |u, st, i: i32| {
        st.picker_tab = i.max(0) as usize;
        u.global::<App>().set_picker_tab(i);
        search_items(&u, st);
    });
    on!(ui, state, on_search_picker, |u, st, q: SharedString| {
        st.picker_query = q.to_string();
        search_items(&u, st);
    });
    on!(ui, state, on_pick, |u, st, id: i32| {
        match st.target {
            Target::Class => {
                let Some(cat) = st.catalog() else { return };
                let Some(class) = cat.class(id as i64).cloned() else { return };
                let level = st.save.as_ref().and_then(|s| s.creature(st.who())).map(creature::level).unwrap_or(1);
                let need = cat.xp_for(level + 1);
                u.global::<App>().set_overlay(0);
                st.target = Target::None;
                edit_who(&u, st, "class", |c| {
                    creature::add_class(c, &class, need);
                });
                fill_editor(&u, st);
            }
            Target::Inventory => {
                let like = st.save.as_ref().and_then(|s| s.inventory().first().cloned());
                if let Some(item) = new_item(st, id.max(0) as usize, like.as_ref()) {
                    if let Some(save) = st.save.as_mut() {
                        save.edit_inventory(&format!("add{}", id), |items| items.push(item));
                    }
                    u.global::<App>().set_overlay_note(s("Added. Add more, or close."));
                    refresh_after_edit(&u, st);
                }
            }
            Target::Container => {
                let Some((list, index)) = st.selected_box else { return };
                let like = st
                    .save
                    .as_ref()
                    .and_then(|s| s.area_git())
                    .and_then(|g| area::container(&g.root, list, index))
                    .and_then(|c| c.list("ItemList"))
                    .and_then(|l| l.first().cloned());
                let Some(mut item) = new_item(st, id.max(0) as usize, like.as_ref()) else { return };
                if let Some(save) = st.save.as_mut() {
                    save.edit_area(&format!("box{}{}", list, index), |git| {
                        let next = area::next_object_id(git);
                        if let Some(c) = area::container_mut(git, list, index) {
                            if c.list("ItemList").is_none() {
                                c.set("ItemList", Value::List(Vec::new()));
                            }
                            let items = c.list_mut("ItemList").unwrap();
                            if list == area::STORES {
                                item.id = items.len() as u32;
                                if like.as_ref().map_or(false, |l| l.get("Infinite").is_some()) && item.get("Infinite").is_none() {
                                    item.fields.insert(0, ("Infinite".into(), Value::Byte(0)));
                                }
                                item.fields.retain(|(l, _)| l != "ObjectId");
                            } else {
                                item.set("ObjectId", Value::Dword(next));
                            }
                            items.push(item);
                        }
                    });
                }
                u.global::<App>().set_overlay_note(s("Added. Add more, or close."));
                refresh_after_edit(&u, st);
            }
            _ => {}
        }
    });
    on!(ui, state, on_pick_save, |u, st, i: i32| {
        let Some(folder) = st.other_saves.get(i.max(0) as usize).cloned() else { return };
        let target = st.target;
        u.global::<App>().set_overlay(0);
        st.target = Target::None;
        match target {
            Target::Compare => match Save::open(&folder.path) {
                Ok(other) => {
                    let list = other.globals.as_ref().map(|g| globals::list(&g.root)).unwrap_or_default();
                    let name = save::summary(&folder.path).map(|x| x.name).unwrap_or_default();
                    st.compare = Some((name, list));
                    st.global_filter.1 = true;
                    fill_globals(&u, st);
                }
                Err(e) => message(&u, "That save could not be opened", &e),
            },
            Target::ImportNpc(n) => match Save::open(&folder.path) {
                Ok(other) => {
                    let result = st.save.as_mut().map(|s| s.import_npc(&other, n));
                    if let Some(Err(e)) = result {
                        message(&u, "They could not be brought over", &e);
                    }
                    let tab = st.tab;
                    fill_editor(&u, st);
                    st.tab = tab;
                }
                Err(e) => message(&u, "That save could not be opened", &e),
            },
            _ => {}
        }
    });

    let _ = with(&ui, &state, |_, _| {});
    ui.run().expect("the window closed with an error");
    let mut st = state.borrow_mut();
    st.settings.light = !ui.global::<Theme>().get_dark();
    st.settings.store();
}
