//! What the installed game offers, as lists with names: classes, feats, Force powers,
//! skills, portraits, NPCs, item templates and global variables. Built from the game's
//! own tables and strings (and mods in Override), so a modded game shows its mods.

use crate::formats::erf::RES_TYPE_UTI;
use crate::formats::gff::{Struct, Value};
use crate::gamedata::GameData;
use crate::games::Game;

#[derive(Clone, Debug)]
pub struct Entry {
    pub id: i64,
    pub name: String,
    pub description: String,
}

#[derive(Clone, Debug)]
pub struct Class {
    pub id: i64,
    pub name: String,
    pub hit_die: i64,
    pub force_die: i64,
    pub droid: bool,
}

#[derive(Clone, Debug)]
pub struct Portrait {
    pub id: i64,
    pub resref: String,
    pub female: bool,
    /// Bodies for the three builds character creation offers: small, medium, large.
    pub bodies: [i64; 3],
}

#[derive(Clone, Debug)]
pub struct ItemTemplate {
    pub resref: String,
    pub name: String,
    pub base_item: i64,
    pub kind: String,
}

pub struct Catalog {
    pub game: Game,
    pub classes: Vec<Class>,
    pub feats: Vec<Entry>,
    pub powers: Vec<Entry>,
    pub skills: Vec<Entry>,
    pub portraits: Vec<Portrait>,
    pub npc_names: Vec<String>,
    /// XP needed for each level, from exptable.2da: index 0 is level 1.
    pub xp_table: Vec<i64>,
}

fn clean(name: String) -> String {
    name.replace('\n', " ").trim().to_string()
}

impl Catalog {
    pub fn build(data: &GameData) -> Catalog {
        let classes_t = data.table("classes");
        let classes = (0..classes_t.rows.len())
            .filter_map(|r| {
                let name = data.row_name("classes", r)?;
                let label = classes_t.cell(r, "label").unwrap_or("").to_ascii_lowercase();
                Some(Class {
                    id: r as i64,
                    name: clean(name),
                    hit_die: classes_t.int(r, "hitdie").unwrap_or(0),
                    force_die: classes_t.int(r, "forcedie").unwrap_or(0),
                    droid: label.contains("droid"),
                })
            })
            .collect();

        let named = |table: &str, desc: &str, keep: &dyn Fn(usize) -> bool| -> Vec<Entry> {
            let t = data.table(table);
            let mut out: Vec<Entry> = (0..t.rows.len())
                .filter(|&r| keep(r))
                .filter_map(|r| {
                    let strref = t.int(r, "name")?;
                    let name = data.string(strref as u32)?;
                    if name.trim().is_empty() || name == "Bad StrRef" {
                        return None;
                    }
                    Some(Entry {
                        id: r as i64,
                        name: clean(name),
                        description: data.row_description(table, r, desc).unwrap_or_default(),
                    })
                })
                .collect();
            out.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
            out
        };
        let feats = named("feat", "description", &|_| true);
        let spells = data.table("spells");
        let powers = named("spells", "spelldesc", &|r| spells.int(r, "usertype") == Some(1));
        let skills_t = data.table("skills");
        let skills = (0..skills_t.rows.len())
            .map(|r| Entry {
                id: r as i64,
                name: data.row_name("skills", r).map(clean).unwrap_or_else(|| format!("Skill {}", r)),
                description: data.row_description("skills", r, "description").unwrap_or_default(),
            })
            .collect();

        let p = data.table("portraits");
        let portraits = (0..p.rows.len())
            .filter_map(|r| {
                let resref = p.cell(r, "baseresref")?.to_string();
                if p.int(r, "forpc") != Some(1) {
                    return None;
                }
                let mid = p.int(r, "appearancenumber")?;
                Some(Portrait {
                    id: r as i64,
                    resref,
                    female: p.int(r, "sex") == Some(1),
                    bodies: [p.int(r, "appearance_s").unwrap_or(mid), mid, p.int(r, "appearance_l").unwrap_or(mid)],
                })
            })
            .collect();

        let npc_names = match data.game {
            Game::K1 => ["Bastila", "Canderous", "Carth", "HK-47", "Jolee", "Juhani", "Mission", "T3-M4", "Zaalbar"]
                .iter()
                .map(|s| s.to_string())
                .collect(),
            Game::K2 => [
                "Atton", "Bao-Dur", "Mandalore", "G0-T0", "Handmaiden", "HK-47", "Kreia", "Mira", "T3-M4",
                "Visas Marr", "Hanharr", "Disciple",
            ]
            .iter()
            .map(|s| s.to_string())
            .collect(),
        };

        let x = data.table("exptable");
        let xp_table: Vec<i64> = (0..x.rows.len())
            .filter_map(|r| x.int(r, "xp").filter(|&v| v >= 0 && v < u32::MAX as i64))
            .collect();

        Catalog { game: data.game, classes, feats, powers, skills, portraits, npc_names, xp_table }
    }

    pub fn class(&self, id: i64) -> Option<&Class> {
        self.classes.iter().find(|c| c.id == id)
    }

    pub fn is_force_class(&self, id: i64) -> bool {
        self.class(id).map_or(false, |c| c.force_die > 0)
    }

    pub fn feat_name(&self, id: i64) -> String {
        self.feats.iter().find(|f| f.id == id).map(|f| f.name.clone()).unwrap_or_else(|| format!("Feat {}", id))
    }

    pub fn power_name(&self, id: i64) -> String {
        self.powers.iter().find(|f| f.id == id).map(|f| f.name.clone()).unwrap_or_else(|| format!("Power {}", id))
    }

    pub fn class_name(&self, id: i64) -> String {
        self.class(id).map(|c| c.name.clone()).unwrap_or_else(|| format!("Class {}", id))
    }

    /// The level reached with this much XP.
    pub fn level_for(&self, xp: i64) -> i64 {
        self.xp_table.iter().filter(|&&need| xp >= need).count().max(1) as i64
    }

    pub fn xp_for(&self, level: i64) -> Option<i64> {
        self.xp_table.get((level - 1).max(0) as usize).copied()
    }

    pub fn max_level(&self) -> i64 {
        self.xp_table.len() as i64
    }

    pub fn portrait_for(&self, id: i64) -> Option<&Portrait> {
        self.portraits.iter().find(|p| p.id == id)
    }
}

/// Every item the game can make, with its name and kind, read from the item templates
/// (several thousand; read on first use).
pub fn item_templates(data: &GameData) -> Vec<ItemTemplate> {
    let base = data.table("baseitems");
    let mut out = Vec::new();
    for resref in data.resource_names("uti", RES_TYPE_UTI) {
        let Some(g) = data.gff(&resref, "uti", RES_TYPE_UTI) else { continue };
        let name = match g.root.get("LocalizedName") {
            Some(Value::LocString(l)) => data.loc(l),
            _ => String::new(),
        };
        let name = clean(name);
        if name.is_empty() || name == "Bad StrRef" {
            continue;
        }
        let base_item = g.root.int("BaseItem").unwrap_or(0);
        let kind = base
            .int(base_item as usize, "name")
            .and_then(|s| data.string(s as u32))
            .unwrap_or_default();
        out.push(ItemTemplate { resref, name, base_item, kind: clean(kind) });
    }
    out.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()).then(a.resref.cmp(&b.resref)));
    out
}

/// A template made into an item as a save holds it: the template's own fields minus
/// those only the toolset uses, with the save-only fields shaped like `like` (an item
/// already in the save) or the game's defaults.
pub fn item_from_template(template: &Struct, like: Option<&Struct>, stack: i64) -> Struct {
    const TOOLSET_ONLY: [&str; 4] = ["TemplateResRef", "Comment", "PaletteID", "UpgradeLevel_"];
    let mut item = Struct::new(0);
    for (label, value) in &template.fields {
        if !TOOLSET_ONLY.contains(&label.as_str()) {
            item.fields.push((label.clone(), value.clone()));
        }
    }
    let defaults: [(&str, Value); 9] = [
        ("Dropable", Value::Byte(1)),
        ("Pickpocketable", Value::Byte(0)),
        ("NonEquippable", Value::Byte(0)),
        ("NewItem", Value::Byte(1)),
        ("DELETING", Value::Byte(0)),
        ("Identified", Value::Byte(1)),
        ("XPosition", Value::Float(0.0)),
        ("YPosition", Value::Float(0.0)),
        ("ZPosition", Value::Float(0.0)),
    ];
    for (label, value) in defaults {
        if item.get(label).is_none() {
            let v = like.and_then(|l| l.get(label)).cloned().unwrap_or(value);
            item.fields.push((label.to_string(), v));
        }
    }
    for (label, value) in [("XOrientation", 1.0f32), ("YOrientation", 0.0), ("ZOrientation", 0.0)] {
        if item.get(label).is_none() {
            item.fields.push((label.to_string(), Value::Float(value)));
        }
    }
    if let Some(l) = like {
        // Field order as the game writes it, for anything both have.
        let order: Vec<&String> = l.fields.iter().map(|(n, _)| n).collect();
        item.fields.sort_by_key(|(n, _)| order.iter().position(|o| *o == n).unwrap_or(usize::MAX));
    }
    item.set_int("StackSize", stack.max(1), Value::Word(1));
    item
}
