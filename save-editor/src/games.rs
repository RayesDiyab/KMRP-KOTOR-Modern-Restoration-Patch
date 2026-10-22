//! Finding the games and their saves without any setup: Steam libraries (Windows, Linux,
//! macOS, Flatpak), GOG and the retail discs through the registry, Windows'
//! VirtualStore copies, KotOR 2's Steam Cloud folder, the Aspyr ports' own folders, and
//! any folder the player adds by hand.

use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Game {
    K1,
    K2,
}

impl Game {
    pub fn title(self) -> &'static str {
        match self {
            Game::K1 => "KotOR",
            Game::K2 => "KotOR II",
        }
    }

    fn steam_folder(self) -> &'static str {
        match self {
            Game::K1 => "swkotor",
            Game::K2 => "Knights of the Old Republic II",
        }
    }

    fn exe(self) -> &'static str {
        match self {
            Game::K1 => "swkotor.exe",
            Game::K2 => "swkotor2.exe",
        }
    }
}

#[derive(Clone, Debug)]
pub struct Install {
    pub game: Game,
    pub path: PathBuf,
    pub source: String,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SaveKind {
    Local,
    Cloud,
    Added,
}

#[derive(Clone, Debug)]
pub struct SaveFolder {
    pub game: Game,
    pub path: PathBuf,
    pub kind: SaveKind,
}

fn home() -> Option<PathBuf> {
    std::env::var_os("HOME").or_else(|| std::env::var_os("USERPROFILE")).map(PathBuf::from)
}

/// Where the editor keeps its settings and the backups of every save it writes:
/// %LOCALAPPDATA%\KMRP\Save Editor, ~/Library/Application Support/KMRP/Save Editor, or
/// $XDG_DATA_HOME/KMRP/Save Editor. Never inside the game folder.
pub fn data_dir() -> PathBuf {
    let base = if cfg!(windows) {
        std::env::var_os("LOCALAPPDATA").map(PathBuf::from)
    } else if cfg!(target_os = "macos") {
        home().map(|h| h.join("Library/Application Support"))
    } else {
        std::env::var_os("XDG_DATA_HOME")
            .map(PathBuf::from)
            .or_else(|| home().map(|h| h.join(".local/share")))
    };
    base.unwrap_or_else(std::env::temp_dir).join("KMRP").join("Save Editor")
}

/// The real path without Windows' \\?\ prefix, so it reads as the player knows it.
pub fn clean(path: &Path) -> PathBuf {
    let real = fs::canonicalize(path).unwrap_or_else(|_| path.to_path_buf());
    let text = real.to_string_lossy().to_string();
    match text.strip_prefix(r"\\?\") {
        Some(rest) if !rest.starts_with("UNC") => PathBuf::from(rest),
        _ => real,
    }
}

fn is_install(game: Game, path: &Path) -> bool {
    path.join("chitin.key").is_file()
        && (path.join(game.exe()).is_file()
            || fs::read_dir(path).map_or(false, |d| {
                d.filter_map(|e| e.ok()).any(|e| {
                    let n = e.file_name().to_string_lossy().to_ascii_lowercase();
                    n.starts_with(&game.exe()[..game.exe().len() - 4]) || n.ends_with(".app")
                })
            }))
}

/// Which game a folder holds, by its executable or, for the ports, its dialog.tlk size.
pub fn identify(path: &Path) -> Option<Game> {
    if !path.join("chitin.key").is_file() {
        return None;
    }
    if path.join("swkotor2.exe").is_file() || path.join("swkotor2.ini").is_file() {
        return Some(Game::K2);
    }
    if path.join("swkotor.exe").is_file() || path.join("swkotor.ini").is_file() {
        return Some(Game::K1);
    }
    // KotOR 2's ports name things differently; its chitin.key lists far more resources.
    let len = fs::metadata(path.join("chitin.key")).map(|m| m.len()).unwrap_or(0);
    Some(if len > 700_000 { Game::K2 } else { Game::K1 })
}

fn steam_roots() -> Vec<PathBuf> {
    let mut roots = Vec::new();
    #[cfg(windows)]
    {
        use winreg::enums::*;
        use winreg::RegKey;
        if let Ok(key) = RegKey::predef(HKEY_CURRENT_USER).open_subkey("Software\\Valve\\Steam") {
            if let Ok(p) = key.get_value::<String, _>("SteamPath") {
                roots.push(PathBuf::from(p));
            }
        }
        for v in ["ProgramFiles(x86)", "ProgramFiles"] {
            if let Some(p) = std::env::var_os(v) {
                roots.push(PathBuf::from(p).join("Steam"));
            }
        }
    }
    if let Some(h) = home() {
        roots.push(h.join(".steam/steam"));
        roots.push(h.join(".local/share/Steam"));
        roots.push(h.join(".var/app/com.valvesoftware.Steam/.local/share/Steam"));
        roots.push(h.join("Library/Application Support/Steam"));
    }
    roots
}

/// Every Steam library folder, from each Steam root's libraryfolders.vdf.
fn steam_libraries() -> Vec<PathBuf> {
    let mut libraries: Vec<PathBuf> = Vec::new();
    for root in steam_roots() {
        let vdf = root.join("steamapps").join("libraryfolders.vdf");
        let mut found = vec![root.clone()];
        if let Ok(text) = fs::read_to_string(&vdf) {
            for line in text.lines() {
                let parts: Vec<&str> = line.split('"').collect();
                if parts.len() >= 4 && parts[1].eq_ignore_ascii_case("path") {
                    found.push(PathBuf::from(parts[3].replace("\\\\", "\\")));
                }
            }
        }
        for f in found {
            let canonical = clean(&f);
            if canonical.is_dir() && !libraries.contains(&canonical) {
                libraries.push(canonical);
            }
        }
    }
    libraries
}

#[cfg(windows)]
fn registry_installs() -> Vec<(Game, PathBuf, &'static str)> {
    use winreg::enums::*;
    use winreg::RegKey;
    let hklm = RegKey::predef(HKEY_LOCAL_MACHINE);
    let mut out = Vec::new();
    let places: [(Game, &str, &str, &'static str); 6] = [
        (Game::K1, "SOFTWARE\\WOW6432Node\\GOG.com\\Games\\1207666283", "path", "GOG"),
        (Game::K2, "SOFTWARE\\WOW6432Node\\GOG.com\\Games\\1421404581", "path", "GOG"),
        (Game::K1, "SOFTWARE\\WOW6432Node\\BioWare\\SW\\KOTOR", "Path", "Disc"),
        (Game::K1, "SOFTWARE\\BioWare\\SW\\KOTOR", "Path", "Disc"),
        (Game::K2, "SOFTWARE\\WOW6432Node\\LucasArts\\KotOR2", "Path", "Disc"),
        (Game::K2, "SOFTWARE\\LucasArts\\KotOR2", "Path", "Disc"),
    ];
    for (game, key, value, source) in places {
        if let Ok(k) = hklm.open_subkey(key) {
            if let Ok(p) = k.get_value::<String, _>(value) {
                out.push((game, PathBuf::from(p), source));
            }
        }
    }
    out
}

#[cfg(not(windows))]
fn registry_installs() -> Vec<(Game, PathBuf, &'static str)> {
    Vec::new()
}

pub fn find_installs(extra: &[PathBuf]) -> Vec<Install> {
    let mut installs: Vec<Install> = Vec::new();
    let mut add = |game: Game, path: PathBuf, source: &str| {
        let path = clean(&path);
        if is_install(game, &path) && !installs.iter().any(|i| i.path == path) {
            installs.push(Install { game, path, source: source.to_string() });
        }
    };
    for library in steam_libraries() {
        for game in [Game::K1, Game::K2] {
            add(game, library.join("steamapps").join("common").join(game.steam_folder()), "Steam");
        }
    }
    for (game, path, source) in registry_installs() {
        add(game, path, source);
    }
    if let Some(h) = home() {
        // The Aspyr ports keep their files inside the app bundle on macOS.
        for (game, rel) in [
            (Game::K1, "Library/Application Support/Steam/steamapps/common/swkotor/KOTOR.app/Contents/KOTOR Data"),
            (Game::K2, "Library/Application Support/Steam/steamapps/common/Knights of the Old Republic II/KOTOR2.app/Contents/GameData"),
        ] {
            add(game, h.join(rel), "Steam");
        }
    }
    for path in extra {
        if let Some(game) = identify(path) {
            add(game, path.clone(), "Added");
        }
    }
    installs
}

fn child_ci(dir: &Path, name: &str) -> Option<PathBuf> {
    fs::read_dir(dir)
        .ok()?
        .filter_map(|e| e.ok())
        .find(|e| e.file_name().to_string_lossy().eq_ignore_ascii_case(name) && e.path().is_dir())
        .map(|e| e.path())
}

pub fn is_save_folder(path: &Path) -> bool {
    path.is_dir()
        && fs::read_dir(path).map_or(false, |d| {
            d.filter_map(|e| e.ok()).any(|e| e.file_name().to_string_lossy().eq_ignore_ascii_case("savenfo.res"))
        })
}

fn saves_in(dir: &Path, game: Game, kind: SaveKind, out: &mut Vec<SaveFolder>) {
    let Ok(entries) = fs::read_dir(dir) else { return };
    for entry in entries.filter_map(|e| e.ok()) {
        let path = entry.path();
        if is_save_folder(&path) && !out.iter().any(|s| s.path == path) {
            out.push(SaveFolder { game, path, kind });
        }
    }
}

/// Folders that hold save folders for an install: its own saves folder, the
/// VirtualStore copy Windows makes for a game under Program Files, and KotOR 2's
/// cloudsaves\<account> folders.
pub fn save_roots(install: &Install) -> Vec<(PathBuf, SaveKind)> {
    let mut roots = Vec::new();
    if let Some(s) = child_ci(&install.path, "saves") {
        roots.push((s, SaveKind::Local));
    }
    if cfg!(windows) {
        if let (Some(local), Some(rest)) = (std::env::var_os("LOCALAPPDATA"), virtual_store_rest(&install.path)) {
            let store = PathBuf::from(local).join("VirtualStore").join(rest);
            if let Some(s) = child_ci(&store, "saves") {
                roots.push((s, SaveKind::Local));
            }
        }
    }
    if let Some(cloud) = child_ci(&install.path, "cloudsaves") {
        if let Ok(accounts) = fs::read_dir(&cloud) {
            for a in accounts.filter_map(|e| e.ok()).filter(|e| e.path().is_dir()) {
                roots.push((a.path(), SaveKind::Cloud));
            }
        }
    }
    roots
}

fn virtual_store_rest(path: &Path) -> Option<PathBuf> {
    // C:\Program Files (x86)\LucasArts\SWKotOR is redirected to
    // %LOCALAPPDATA%\VirtualStore\Program Files (x86)\LucasArts\SWKotOR.
    let text = path.to_string_lossy().trim_start_matches("\\\\?\\").to_string();
    if text.get(1..).map_or(false, |r| r.to_ascii_lowercase().starts_with(":\\program files")) {
        Some(PathBuf::from(&text[3..]))
    } else {
        None
    }
}

/// The Aspyr ports' own save folders, which live outside the game.
fn port_save_roots(game: Game) -> Vec<PathBuf> {
    let Some(h) = home() else { return Vec::new() };
    match game {
        Game::K1 => vec![
            h.join("Library/Application Support/Knights of the Old Republic/saves"),
            h.join("Library/Containers/com.aspyr.kotor/Data/Library/Application Support/KOTOR/saves"),
        ],
        Game::K2 => vec![
            h.join(".local/share/aspyr-media/kotor2/saves"),
            h.join("Library/Application Support/Star Wars Knights of the Old Republic II/saves"),
            h.join("Library/Application Support/Aspyr/Star Wars Knights of the Old Republic II/saves"),
        ],
    }
}

pub fn find_saves(installs: &[Install], game: Game, added: &[PathBuf]) -> Vec<SaveFolder> {
    let mut out = Vec::new();
    for install in installs.iter().filter(|i| i.game == game) {
        for (root, kind) in save_roots(install) {
            saves_in(&root, game, kind, &mut out);
        }
    }
    for root in port_save_roots(game) {
        saves_in(&root, game, SaveKind::Local, &mut out);
    }
    for path in added {
        if is_save_folder(path) {
            if crate::save::peek_game(path) == Some(game) && !out.iter().any(|s| &s.path == path) {
                out.push(SaveFolder { game, path: path.clone(), kind: SaveKind::Added });
            }
        } else {
            saves_in(path, game, SaveKind::Added, &mut out);
            out.retain(|s| s.kind != SaveKind::Added || crate::save::peek_game(&s.path) == Some(game));
        }
    }
    out
}
