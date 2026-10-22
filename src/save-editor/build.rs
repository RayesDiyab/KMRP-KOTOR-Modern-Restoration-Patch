//! Compiles the interface (ui/app.slint) into the program.
//!
//! The interface is set in KMRP's own Original HD Font. Its OTF files are made by
//! tools/build_hd_original_otf.py into build/fonts and never committed; that tool needs
//! the game's own font atlases (build/native-runtime/original-fonts), so a machine
//! without them (a CI runner) cannot make them. This script writes kmrp-fonts.slint into
//! the build folder: it embeds the fonts when they exist or can be made, and is empty
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

fn fonts_dir(root: &Path) -> Option<PathBuf> {
    let dir = root.join("build/fonts/KMRP-OriginalHD-OTF");
    let present = |d: &Path| FONTS.iter().all(|f| d.join(f).is_file());
    if present(&dir) {
        return Some(dir);
    }
    if !root.join("build/native-runtime/original-fonts").is_dir() {
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
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    let root = root.canonicalize().unwrap_or(root);
    let out = PathBuf::from(std::env::var("OUT_DIR").unwrap());
    println!("cargo:rerun-if-changed=ui");
    println!("cargo:rerun-if-changed={}", root.join("build/fonts/KMRP-OriginalHD-OTF").display());

    let mut slint = String::from("// Written by build.rs.\n");
    match fonts_dir(&root) {
        Some(dir) => {
            for f in FONTS {
                let path = dir.join(f).to_string_lossy().replace('\\', "/");
                let path = path.trim_start_matches("//?/").to_string();
                slint.push_str(&format!("import \"{}\";\n", path));
            }
        }
        None => println!(
            "cargo:warning=KMRP's fonts are not in build/fonts and cannot be made here (the game's font atlases are missing); the window uses the system font"
        ),
    }
    slint.push_str("export global KmrpFonts { }\n");
    std::fs::write(out.join("kmrp-fonts.slint"), slint).unwrap();

    let config = slint_build::CompilerConfiguration::new().with_include_paths(vec![out.clone()]);
    slint_build::compile_with_config("ui/app.slint", config).expect("the user interface did not compile");

    #[cfg(windows)]
    {
        let mut res = winresource::WindowsResource::new();
        res.set_icon("../patcher/favicon.ico");
        res.set("ProductName", "KMRP Save Editor");
        res.set("FileDescription", "KMRP Save Editor");
        res.set("CompanyName", "RaymanGT");
        let _ = res.compile();
    }
}
