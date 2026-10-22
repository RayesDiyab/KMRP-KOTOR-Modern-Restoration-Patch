//! Development aid: lists the resource types in a module's archives.
//!   cargo run --example module_probe -- <game folder> <module>
use kse_core::formats::rim::Rim;
use kse_core::formats::tables::find_case_insensitive;
use std::collections::BTreeMap;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&args[1]);
    for suffix in [".rim", "_s.rim"] {
        let Some(p) = find_case_insensitive(&root, &format!("modules/{}{}", args[2], suffix)) else { continue };
        let Some(r) = Rim::open(&p) else { println!("{}: not a rim", p.display()); continue };
        let mut by: BTreeMap<u16, Vec<String>> = BTreeMap::new();
        for (n, k) in r.kinds() {
            by.entry(k).or_default().push(n);
        }
        println!("{}", p.display());
        for (k, v) in by {
            println!("  {} x{}: {:?}", k, v.len(), &v[..v.len().min(5)]);
        }
    }
}
