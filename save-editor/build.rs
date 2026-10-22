//! Compiles the interface (ui/app.slint) into the program.
//!
//! This folder builds on its own, outside KMRP. The interface is set in the KMRP
//! Original HD fonts (KMRP's fonts/, SIL Open Font License 1.1), four of which are
//! committed in fonts/ here with their licence. The folder KMRP_FONTS names is used
//! instead when it holds them all. This script writes kmrp-fonts.slint into the build
//! folder, embedding the fonts; without them it is empty, the window falls back to the
//! system's font and Cargo prints a warning.

use std::path::{Path, PathBuf};

const FONTS: [&str; 4] = [
    "KMRP-OriginalHD-Menu.otf",
    "KMRP-OriginalHD-MenuMedium.otf",
    "KMRP-OriginalHD-MenuSmallB.otf",
    "KMRP-OriginalHD-Descriptions.otf",
];

fn fonts_dir(here: &Path) -> Option<PathBuf> {
    let present = |d: &Path| FONTS.iter().all(|f| d.join(f).is_file());
    let named = std::env::var_os("KMRP_FONTS").map(PathBuf::from);
    named.into_iter().chain([here.join("fonts")]).find(|d| present(d))
}

fn main() {
    let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    println!("cargo:rerun-if-changed=ui");
    println!("cargo:rerun-if-changed=fonts");
    println!("cargo:rerun-if-env-changed=KMRP_FONTS");

    // The quest databases in data/quests (k1-*.json, k2-*.json), compiled in; questdb.rs
    // includes the list written here.
    println!("cargo:rerun-if-changed=data/quests");
    let mut files: Vec<PathBuf> = std::fs::read_dir(here.join("data").join("quests"))
        .map(|d| d.filter_map(|e| e.ok()).map(|e| e.path()).filter(|p| p.extension().map_or(false, |x| x == "json")).collect())
        .unwrap_or_default();
    files.sort();
    let mut list = String::from("&[\n");
    for f in &files {
        let name = f.file_name().unwrap().to_string_lossy().to_lowercase();
        let game = if name.starts_with("k2") { "Game::K2" } else { "Game::K1" };
        list.push_str(&format!("    ({}, include_str!({:?})),\n", game, f.display().to_string()));
    }
    list.push_str("]\n");
    std::fs::write(out.join("quest_files.rs"), list).unwrap();

    let mut slint = String::from("// Written by build.rs.\n");
    match fonts_dir(&here) {
        Some(dir) => {
            for f in FONTS {
                let path = dir.join(f).to_string_lossy().replace('\\', "/");
                let path = path.trim_start_matches("//?/").to_string();
                slint.push_str(&format!("import \"{}\";\n", path));
            }
        }
        None => println!(
            "cargo:warning=KMRP's fonts are not in fonts/ (or KMRP_FONTS); the window uses the system font"
        ),
    }
    slint.push_str("export global KmrpFonts { }\n");
    std::fs::write(out.join("kmrp-fonts.slint"), slint).unwrap();

    let config = slint_build::CompilerConfiguration::new().with_include_paths(vec![out.clone()]);
    slint_build::compile_with_config("ui/app.slint", config).expect("the user interface did not compile");

    #[cfg(windows)]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("assets/save-editor.ico");
        res.set("ProductName", "KMRP Save Editor");
        res.set("FileDescription", "KMRP Save Editor");
        res.set("CompanyName", "RaymanGT");
        let _ = res.compile();
    }
}
