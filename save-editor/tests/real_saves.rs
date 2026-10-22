//! Every save found on this machine, read only: each GFF and archive must come back the
//! same after being written and read again, and the save model must open it. Saves are
//! never written here. Skipped when no game is installed.

use kse_core::formats::erf::{Erf, RES_TYPE_SAV};
use kse_core::formats::gff::Gff;
use kse_core::games::{find_installs, find_saves, Game};
use kse_core::save::Save;
use std::fs;

fn check_gff(name: &str, data: &[u8], stats: &mut (usize, usize)) {
    let Ok(gff) = Gff::read(data) else { return };
    let written = gff.write();
    let again = Gff::read(&written).unwrap_or_else(|e| panic!("{}: written file unreadable: {}", name, e));
    assert_eq!(gff, again, "{} changed in a round trip", name);
    stats.0 += 1;
    if written == data {
        stats.1 += 1;
    }
}

fn check_erf(name: &str, data: &[u8], stats: &mut (usize, usize)) {
    let erf = Erf::read(data).unwrap_or_else(|e| panic!("{}: {}", name, e));
    let again = Erf::read(&erf.write()).unwrap();
    assert_eq!(erf.resources, again.resources, "{} changed in a round trip", name);
    for r in &erf.resources {
        let n = format!("{}/{}.{}", name, r.name, r.kind);
        if r.kind == RES_TYPE_SAV {
            check_erf(&n, &r.data, stats);
        } else {
            check_gff(&n, &r.data, stats);
        }
    }
}

#[test]
fn every_save_round_trips() {
    let installs = find_installs(&[]);
    let mut total = 0;
    for game in [Game::K1, Game::K2] {
        for save in find_saves(&installs, game, &[]) {
            let mut stats = (0, 0);
            for entry in fs::read_dir(&save.path).unwrap().filter_map(|e| e.ok()) {
                let name = entry.file_name().to_string_lossy().to_string();
                let data = fs::read(entry.path()).unwrap();
                if name.to_ascii_lowercase().ends_with(".res") {
                    check_gff(&name, &data, &mut stats);
                } else if name.to_ascii_lowercase().ends_with(".sav") {
                    check_erf(&name, &data, &mut stats);
                }
            }
            let opened = Save::open(&save.path).map(|s| s.npcs().len());
            println!(
                "{:?} {:?}: {} GFFs, {} byte-identical, opens: {:?}",
                game,
                save.path.file_name().unwrap(),
                stats.0,
                stats.1,
                opened
            );
            assert!(opened.is_ok(), "{}: {:?}", save.path.display(), opened.err());
            total += 1;
        }
    }
    println!("{} saves checked", total);
}
