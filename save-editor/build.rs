//! Compiles the interface (ui/app.slint) into the program.
//!
//! This folder builds on its own, outside KMRP. The interface is set in KMRP's own
//! Original HD Font. Its OTF files are made by KMRP's tools/build_hd_original_otf.py
//! from the game's own font atlases and never committed, so they are looked for, in
//! order: the folder KMRP_FONTS names; fonts/ in this folder; and, when this folder sits
//! in a KMRP checkout, its build/fonts/KMRP-OriginalHD-OTF (made there by the tool if
//! the game's atlases are in build/native-runtime/original-fonts). This script writes
//! kmrp-fonts.slint into the build folder: it embeds the fonts when found, and is empty
//! otherwise, in which case the window falls back to the system's font and Cargo prints a
//! warning. Release builds are made where the fonts exist.

use std::path::{Path, PathBuf};
use std::process::Command;

const FONTS: [&str; 4] = [
    "KMRP-OriginalHD-Menu.otf",
    "KMRP-OriginalHD-MenuMedium.otf",
    "KMRP-OriginalHD-MenuSmallB.otf",
    "KMRP-OriginalHD-Descriptions.otf",
];

fn fonts_dir(here: &Path, kmrp: &Path) -> Option<PathBuf> {
    let present = |d: &Path| FONTS.iter().all(|f| d.join(f).is_file());
    let named = std::env::var_os("KMRP_FONTS").map(PathBuf::from);
    let dir = kmrp.join("build/fonts/KMRP-OriginalHD-OTF");
    for d in named.into_iter().chain([here.join("fonts"), dir.clone()]) {
        if present(&d) {
            return Some(d);
        }
    }
    // Inside a KMRP checkout with the game's font atlases, the fonts can be made.
    let root = kmrp;
    if !root.join("tools/build_hd_original_otf.py").is_file() || !root.join("build/native-runtime/original-fonts").is_dir() {
        return None;
    }
    let python = std::env::var("PYTHON").unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() });
    let made = Command::new(python)
        .arg(root.join("tools/build_hd_original_otf.py"))
        .current_dir(root)
        .status()
        .map_or(false, |s| s.success());
    (made && present(&dir)).then_some(dir)
}

fn main() {
    let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let kmrp = here.join("..");
    let kmrp = kmrp.canonicalize().unwrap_or(kmrp);
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    println!("cargo:rerun-if-changed=ui");
    println!("cargo:rerun-if-changed=fonts");
    println!("cargo:rerun-if-env-changed=KMRP_FONTS");
    println!("cargo:rerun-if-changed={}", kmrp.join("build/fonts/KMRP-OriginalHD-OTF").display());

    let mut slint = String::from("// Written by build.rs.\n");
    match fonts_dir(&here, &kmrp) {
        Some(dir) => {
            for f in FONTS {
                let path = dir.join(f).to_string_lossy().replace('\\', "/");
                let path = path.trim_start_matches("//?/").to_string();
                slint.push_str(&format!("import \"{}\";\n", path));
            }
        }
        None => println!(
            "cargo:warning=KMRP's fonts were not found (KMRP_FONTS, fonts/ here, or a KMRP checkout's build/fonts) and cannot be made here; the window uses the system font"
        ),
    }
    slint.push_str("export global KmrpFonts { }\n");
    std::fs::write(out.join("kmrp-fonts.slint"), slint).unwrap();

    let config = slint_build::CompilerConfiguration::new().with_include_paths(vec![out.clone()]);
    slint_build::compile_with_config("ui/app.slint", config).expect("the user interface did not compile");

    #[cfg(windows)]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("assets/favicon.ico");
        res.set("ProductName", "KMRP Save Editor");
        res.set("FileDescription", "KMRP Save Editor");
        res.set("CompanyName", "RaymanGT");
        let _ = res.compile();
    }
}
