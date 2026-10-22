//! GLOBALVARS.res: the story's switches (booleans), counters (numbers) and strings, each
//! catalogue list paired with its values by position. Booleans are packed most
//! significant bit first; numbers are one byte each (scripts read them signed).

use crate::formats::gff::{Struct, Value};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Boolean,
    Number,
    String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Global {
    pub kind: Kind,
    pub index: usize,
    pub name: String,
    pub value: GlobalValue,
}

#[derive(Clone, Debug, PartialEq)]
pub enum GlobalValue {
    Bool(bool),
    Number(i64),
    Text(String),
}

impl GlobalValue {
    pub fn display(&self) -> String {
        match self {
            GlobalValue::Bool(b) => if *b { "On" } else { "Off" }.to_string(),
            GlobalValue::Number(n) => n.to_string(),
            GlobalValue::Text(t) => t.clone(),
        }
    }
}

fn names(root: &Struct, cat: &str) -> Vec<String> {
    root.list(cat).map(|l| l.iter().map(|s| s.string("Name").unwrap_or_default()).collect()).unwrap_or_default()
}

fn void<'a>(root: &'a Struct, label: &str) -> &'a [u8] {
    match root.get(label) {
        Some(Value::Void(v)) => v,
        _ => &[],
    }
}

pub fn list(root: &Struct) -> Vec<Global> {
    let mut out = Vec::new();
    let bools = void(root, "ValBoolean");
    for (i, name) in names(root, "CatBoolean").into_iter().enumerate() {
        let on = bools.get(i / 8).map_or(false, |b| b & (0x80 >> (i % 8)) != 0);
        out.push(Global { kind: Kind::Boolean, index: i, name, value: GlobalValue::Bool(on) });
    }
    let numbers = void(root, "ValNumber");
    for (i, name) in names(root, "CatNumber").into_iter().enumerate() {
        let n = numbers.get(i).map_or(0, |&b| b as i8 as i64);
        out.push(Global { kind: Kind::Number, index: i, name, value: GlobalValue::Number(n) });
    }
    let strings = root.list("ValString").cloned().unwrap_or_default();
    for (i, name) in names(root, "CatString").into_iter().enumerate() {
        let t = strings.get(i).and_then(|s| s.string("String")).unwrap_or_default();
        out.push(Global { kind: Kind::String, index: i, name, value: GlobalValue::Text(t) });
    }
    out
}

pub fn set_bool(root: &mut Struct, index: usize, on: bool) {
    let count = names(root, "CatBoolean").len();
    let mut bytes = void(root, "ValBoolean").to_vec();
    // The game writes count / 8 + 1 bytes.
    let want = count / 8 + 1;
    if bytes.len() < want {
        bytes.resize(want, 0);
    }
    let mask = 0x80u8 >> (index % 8);
    if on {
        bytes[index / 8] |= mask;
    } else {
        bytes[index / 8] &= !mask;
    }
    root.set("ValBoolean", Value::Void(bytes));
}

/// Numbers are one byte; scripts read -128 to 127.
pub fn set_number(root: &mut Struct, index: usize, value: i64) {
    let mut bytes = void(root, "ValNumber").to_vec();
    if bytes.len() <= index {
        bytes.resize(index + 1, 0);
    }
    bytes[index] = value.clamp(-128, 127) as i8 as u8;
    root.set("ValNumber", Value::Void(bytes));
}

pub fn set_string(root: &mut Struct, index: usize, text: &str) {
    if let Some(list) = root.list_mut("ValString") {
        if let Some(entry) = list.get_mut(index) {
            entry.set("String", Value::String(crate::text::encode(text)));
        }
    }
}

pub fn set(root: &mut Struct, g: &Global, value: &GlobalValue) {
    match value {
        GlobalValue::Bool(b) => set_bool(root, g.index, *b),
        GlobalValue::Number(n) => set_number(root, g.index, *n),
        GlobalValue::Text(t) => set_string(root, g.index, t),
    }
}

/// Each variable whose value differs between two saves, matched by name and kind:
/// (this save's variable, the other save's value).
pub fn compare(this: &[Global], other: &[Global]) -> Vec<(Global, GlobalValue)> {
    let mut out = Vec::new();
    for g in this {
        if let Some(o) = other.iter().find(|o| o.kind == g.kind && o.name == g.name) {
            if o.value != g.value {
                out.push((g.clone(), o.value.clone()));
            }
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn booleans_are_most_significant_bit_first() {
        let mut root = Struct::new(u32::MAX);
        let cat: Vec<Struct> = (0..10)
            .map(|i| {
                let mut s = Struct::new(0);
                s.set("Name", Value::String(format!("v{}", i).into_bytes()));
                s
            })
            .collect();
        root.set("CatBoolean", Value::List(cat));
        root.set("ValBoolean", Value::Void(vec![0b1000_0000, 0b0100_0000]));
        let l = list(&root);
        assert_eq!(l[0].value, GlobalValue::Bool(true));
        assert_eq!(l[9].value, GlobalValue::Bool(true));
        assert_eq!(l[1].value, GlobalValue::Bool(false));
        set_bool(&mut root, 1, true);
        assert_eq!(void(&root, "ValBoolean")[0], 0b1100_0000);
    }
}
