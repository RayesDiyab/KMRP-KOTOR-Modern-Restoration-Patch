//! The game's quests as its journal (global.jrl) describes them, with the experience each
//! stage gives: the quest's plot.2da row's `xp` times the stage's `XP_Percentage` (a
//! fraction; endings of one quest can differ: tat18ac_dragonhunt gives 0.8 at stage 70,
//! 0.2 at 60). The game gives that XP when the journal reaches the stage.

use crate::formats::gff::{Struct, Value};
use crate::gamedata::GameData;

#[derive(Clone, Debug)]
pub struct Stage {
    pub id: i64,
    pub end: bool,
    pub text: String,
    pub xp: i64,
}

#[derive(Clone, Debug)]
pub struct Quest {
    pub tag: String,
    pub name: String,
    pub stages: Vec<Stage>,
}

impl Quest {
    pub fn stage(&self, id: i64) -> Option<&Stage> {
        self.stages.iter().find(|s| s.id == id)
    }

    pub fn endings(&self) -> Vec<&Stage> {
        self.stages.iter().filter(|s| s.end).collect()
    }
}

fn loc(data: &GameData, s: &Struct, label: &str) -> String {
    match s.get(label) {
        Some(Value::LocString(l)) => crate::text::strip_codes(&data.loc(l)),
        _ => String::new(),
    }
}

pub fn all(data: &GameData) -> Vec<Quest> {
    let Some(jrl) = data.gff("global", "jrl", 2056) else { return Vec::new() };
    let plot = data.table("plot");
    let mut out = Vec::new();
    for c in jrl.root.list("Categories").map(|l| l.as_slice()).unwrap_or(&[]) {
        let tag = c.string("Tag").unwrap_or_default();
        if tag.is_empty() {
            continue;
        }
        let plot_xp = c.int("PlotIndex").filter(|&i| i >= 0).and_then(|i| plot.int(i as usize, "xp")).unwrap_or(0);
        let mut stages: Vec<Stage> = c
            .list("EntryList")
            .map(|l| {
                l.iter()
                    .map(|e| Stage {
                        id: e.int("ID").unwrap_or(0),
                        end: e.int("End") == Some(1),
                        text: loc(data, e, "Text"),
                        xp: (plot_xp as f32 * e.float("XP_Percentage").unwrap_or(0.0)).round() as i64,
                    })
                    .collect()
            })
            .unwrap_or_default();
        stages.sort_by_key(|s| s.id);
        let mut name = loc(data, c, "Name");
        if name.trim().is_empty() {
            name = tag.clone();
        }
        out.push(Quest { tag, name, stages });
    }
    out
}
