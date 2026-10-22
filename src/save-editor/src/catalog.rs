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
    /// The icon's texture name (feat.2da `icon`, spells.2da `iconresref`).
    pub icon: String,
    /// The group it is listed under, and that group's place in the list.
    pub group: String,
    pub group_order: usize,
}

/// Feat groups, by feat.2da `toolscategories`.
const FEAT_GROUPS: [(i64, &str); 6] = [
    (3, "Jedi"),
    (2, "Combat"),
    (1, "Weapons and armour"),
    (5, "Class abilities"),
    (6, "Skills and general"),
    (4, "Droid and other"),
];

/// Force power groups, by spells.2da `goodevil`.
const POWER_GROUPS: [(&str, &str); 3] = [("-", "Universal"), ("G", "Light side"), ("E", "Dark side")];

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
    pub icon: String,
    pub category: usize,
}

/// The kinds of item the Add an Item list is split into.
pub const ITEM_CATEGORIES: [&str; 8] =
    ["All", "Weapons", "Grenades", "Armour", "Gear", "Usable", "Upgrades", "Other"];

/// An item's kind from its base item row: worn slots, then its class name.
/// Creature-only items (claws, hides) return None: no player uses them.
pub fn item_category(base: &crate::formats::tables::TwoDa, row: usize) -> Option<usize> {
    let slots = base.int(row, "equipableslots").unwrap_or(0);
    if slots & 0x3C000 != 0 {
        return None;
    }
    let class = base.cell(row, "itemclass").unwrap_or("").to_ascii_lowercase();
    let icon = base.cell(row, "defaulticon").unwrap_or("").to_ascii_lowercase();
    Some(if class.contains("upgrade") || class.contains("sbrcrstl") || icon.contains("crystal") {
        6
    } else if slots & 0x30 != 0 {
        1
    } else if icon.contains("grenade") || icon.contains("rocket") {
        2
    } else if slots & 0x2 != 0 {
        3
    } else if slots != 0 {
        4
    } else if class.starts_with("i_") && !class.contains("credits") && !class.contains("pazcard") && !class.contains("datapad") {
        5
    } else {
        7
    })
}

/// An item's inventory icon, as the game names it: "i" + the base item's class +
/// "_" + the model variation (iw_lghtsbr_001, ia_jedirobe_001), or the base item's
/// default icon when the game has no such texture.
pub fn item_icon(base: &crate::formats::tables::TwoDa, row: usize, variation: i64) -> (String, String) {
    let class = base.cell(row, "itemclass").unwrap_or("").to_ascii_lowercase();
    let fallback = base.cell(row, "defaulticon").unwrap_or("").to_ascii_lowercase();
    (format!("i{}_{:03}", class, variation.max(1)), fallback)
}

/// Orders entries so a chain stands together, first link first (Flurry, Improved
/// Flurry, Master Flurry): by group, then the chain's first entry's name, then depth.
fn chain_sort(entries: &mut Vec<Entry>, parent: &dyn Fn(i64) -> Option<i64>) {
    let names: std::collections::HashMap<i64, String> =
        entries.iter().map(|e| (e.id, e.name.to_lowercase())).collect();
    let key = |e: &Entry| {
        let mut root = e.id;
        let mut depth = 0;
        while let Some(p) = parent(root) {
            if depth > 10 || !names.contains_key(&p) {
                break;
            }
            root = p;
            depth += 1;
        }
        (e.group_order, names.get(&root).cloned().unwrap_or_default(), depth, e.name.to_lowercase())
    };
    entries.sort_by_cached_key(key);
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
                        icon: String::new(),
                        group: String::new(),
                        group_order: 0,
                    })
                })
                .collect();
            out.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
            out
        };
        let feat_t = data.table("feat");
        let mut feats = named("feat", "description", &|_| true);
        for f in feats.iter_mut() {
            let r = f.id as usize;
            f.icon = feat_t.cell(r, "icon").unwrap_or("").to_ascii_lowercase();
            let tc = feat_t.int(r, "toolscategories").unwrap_or(6);
            let g = FEAT_GROUPS.iter().position(|(c, _)| *c == tc).unwrap_or(FEAT_GROUPS.len() - 1);
            f.group_order = g;
            f.group = FEAT_GROUPS[g].1.to_string();
        }
        chain_sort(&mut feats, &|id| feat_t.int(id as usize, "prereqfeat1"));
        let spells = data.table("spells");
        let mut powers = named("spells", "spelldesc", &|r| spells.int(r, "usertype") == Some(1));
        for p in powers.iter_mut() {
            let r = p.id as usize;
            p.icon = spells.cell(r, "iconresref").unwrap_or("").to_ascii_lowercase();
            let ge = spells.cell(r, "goodevil").unwrap_or("-").to_ascii_uppercase();
            let g = POWER_GROUPS.iter().position(|(c, _)| *c == ge).unwrap_or(0);
            p.group_order = g;
            p.group = POWER_GROUPS[g].1.to_string();
        }
        chain_sort(&mut powers, &|id| {
            spells.cell(id as usize, "prerequisites").and_then(|v| v.split('_').next()?.parse().ok())
        });
        let skills_t = data.table("skills");
        let skills = (0..skills_t.rows.len())
            .map(|r| Entry {
                id: r as i64,
                name: data.row_name("skills", r).map(clean).unwrap_or_else(|| format!("Skill {}", r)),
                description: data.row_description("skills", r, "description").unwrap_or_default(),
                icon: skills_t.cell(r, "icon").unwrap_or("").to_ascii_lowercase(),
                group: String::new(),
                group_order: 0,
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
        let Some(category) = item_category(&base, base_item as usize) else { continue };
        let kind = base
            .int(base_item as usize, "name")
            .and_then(|s| data.string(s as u32))
            .unwrap_or_default();
        let (icon, _) = item_icon(&base, base_item as usize, g.root.int("ModelVariation").unwrap_or(1));
        out.push(ItemTemplate { resref, name, base_item, kind: clean(kind), icon, category });
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
