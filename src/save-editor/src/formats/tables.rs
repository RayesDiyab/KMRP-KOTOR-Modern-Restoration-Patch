//! The game's own data, read only: chitin.key and its .bif files, binary 2DA V2.b
//! tables and the TLK V3.0 string table (dialog.tlk).

use super::gff::GffError;
use std::collections::HashMap;
use std::fs;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

fn u32_at(data: &[u8], at: usize) -> Option<u32> {
    data.get(at..at + 4).map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
}

fn u16_at(data: &[u8], at: usize) -> Option<u16> {
    data.get(at..at + 2).map(|b| u16::from_le_bytes([b[0], b[1]]))
}

/// Where chitin.key says each resource lives.
pub struct Key {
    root: PathBuf,
    bifs: Vec<String>,
    entries: HashMap<(String, u16), u32>,
    cache: std::sync::Mutex<HashMap<usize, std::sync::Arc<Bif>>>,
}

struct Bif {
    path: PathBuf,
    entries: Vec<(u32, u32)>,
}

/// `size` bytes at `offset` of a file.
pub fn read_at(path: &Path, offset: u64, size: usize) -> Option<Vec<u8>> {
    let mut file = fs::File::open(path).ok()?;
    file.seek(SeekFrom::Start(offset)).ok()?;
    let mut out = vec![0u8; size];
    file.read_exact(&mut out).ok()?;
    Some(out)
}

impl Key {
    pub fn open(game: &Path) -> Option<Key> {
        let data = fs::read(game.join("chitin.key")).ok()?;
        if data.get(0..8)? != b"KEY V1  " {
            return None;
        }
        let bif_count = u32_at(&data, 8)? as usize;
        let key_count = u32_at(&data, 12)? as usize;
        let files = u32_at(&data, 16)? as usize;
        let keys = u32_at(&data, 20)? as usize;
        let mut bifs = Vec::with_capacity(bif_count);
        for i in 0..bif_count {
            let at = files + i * 12;
            let name_offset = u32_at(&data, at + 4)? as usize;
            let name_size = u16_at(&data, at + 8)? as usize;
            let raw = data.get(name_offset..name_offset + name_size)?;
            let end = raw.iter().position(|&b| b == 0).unwrap_or(raw.len());
            bifs.push(raw[..end].iter().map(|&b| if b == b'\\' { '/' } else { b as char }).collect());
        }
        let mut entries = HashMap::with_capacity(key_count);
        for i in 0..key_count {
            let at = keys + i * 22;
            let raw = data.get(at..at + 16)?;
            let end = raw.iter().position(|&b| b == 0).unwrap_or(16);
            let name: String = raw[..end].iter().map(|&b| (b as char).to_ascii_lowercase()).collect();
            let kind = u16_at(&data, at + 16)?;
            let id = u32_at(&data, at + 18)?;
            entries.insert((name, kind), id);
        }
        Some(Key { root: game.to_path_buf(), bifs, entries, cache: Default::default() })
    }

    /// A BIF's table of (offset, size) for each resource, read once; the resources
    /// themselves are read from the file one at a time, so a large BIF is never held whole.
    fn bif(&self, index: usize) -> Option<std::sync::Arc<Bif>> {
        let mut cache = self.cache.lock().ok()?;
        if let Some(b) = cache.get(&index) {
            return Some(b.clone());
        }
        let path = find_case_insensitive(&self.root, self.bifs.get(index)?)?;
        let mut file = fs::File::open(&path).ok()?;
        let mut head = [0u8; 20];
        file.read_exact(&mut head).ok()?;
        if &head[0..8] != b"BIFFV1  " {
            return None;
        }
        let count = u32_at(&head, 8)? as usize;
        let table = u32_at(&head, 16)? as u64;
        let mut raw = vec![0u8; count * 16];
        file.seek(SeekFrom::Start(table)).ok()?;
        file.read_exact(&mut raw).ok()?;
        let entries = (0..count).map(|i| (u32_at(&raw, i * 16 + 4).unwrap(), u32_at(&raw, i * 16 + 8).unwrap())).collect();
        let bif = std::sync::Arc::new(Bif { path, entries });
        cache.insert(index, bif.clone());
        Some(bif)
    }

    /// Every resource of one type the key lists, by name.
    pub fn names(&self, kind: u16) -> Vec<String> {
        let mut names: Vec<String> = self.entries.keys().filter(|(_, k)| *k == kind).map(|(n, _)| n.clone()).collect();
        names.sort();
        names
    }

    pub fn read(&self, name: &str, kind: u16) -> Option<Vec<u8>> {
        let id = *self.entries.get(&(name.to_ascii_lowercase(), kind))?;
        let bif = self.bif((id >> 20) as usize)?;
        let (offset, size) = *bif.entries.get((id & 0xFFFFF) as usize)?;
        read_at(&bif.path, offset as u64, size as usize)
    }
}

/// Linux and macOS installs keep BioWare's mixed-case names; chitin.key spells them its
/// own way. Each path part is matched without regard to case.
pub fn find_case_insensitive(root: &Path, relative: &str) -> Option<PathBuf> {
    let mut path = root.to_path_buf();
    for part in relative.split(|c| c == '/' || c == '\\').filter(|p| !p.is_empty()) {
        let direct = path.join(part);
        if direct.exists() {
            path = direct;
            continue;
        }
        let found = fs::read_dir(&path)
            .ok()?
            .filter_map(|e| e.ok())
            .find(|e| e.file_name().to_string_lossy().eq_ignore_ascii_case(part))?;
        path = found.path();
    }
    Some(path)
}

#[derive(Default, Clone)]
pub struct TwoDa {
    pub columns: Vec<String>,
    pub rows: Vec<Vec<String>>,
}

impl TwoDa {
    pub fn read(data: &[u8]) -> Result<TwoDa, GffError> {
        let bad = || GffError("not a 2DA V2.b table".into());
        if data.starts_with(b"2DA V2.0") || data.starts_with(b"2DA\tV2.0") {
            return Ok(TwoDa::read_text(data));
        }
        if data.get(0..9) != Some(b"2DA V2.b\n") {
            return Err(bad());
        }
        let mut pos = 9;
        let header_end = pos + data[pos..].iter().position(|&b| b == 0).ok_or_else(bad)?;
        let columns: Vec<String> = data[pos..header_end]
            .split(|&b| b == b'\t')
            .filter(|c| !c.is_empty())
            .map(|c| String::from_utf8_lossy(c).to_ascii_lowercase())
            .collect();
        pos = header_end + 1;
        let row_count = u32_at(data, pos).ok_or_else(bad)? as usize;
        pos += 4;
        for _ in 0..row_count {
            pos += data[pos..].iter().position(|&b| b == b'\t').ok_or_else(bad)? + 1;
        }
        let cells = row_count * columns.len();
        let offsets = pos;
        let blob = offsets + cells * 2 + 2;
        let mut rows = Vec::with_capacity(row_count);
        for r in 0..row_count {
            let mut row = Vec::with_capacity(columns.len());
            for c in 0..columns.len() {
                let off = u16_at(data, offsets + (r * columns.len() + c) * 2).ok_or_else(bad)? as usize;
                let start = blob + off;
                let s = data.get(start..).ok_or_else(bad)?;
                let end = s.iter().position(|&b| b == 0).unwrap_or(s.len());
                row.push(crate::text::decode(&s[..end]));
            }
            rows.push(row);
        }
        Ok(TwoDa { columns, rows })
    }

    /// The text form mods put in Override: a version line, an optional DEFAULT line,
    /// the column names, then one row per line led by its row label. Cells are split
    /// on whitespace; a quoted cell may hold spaces.
    fn read_text(data: &[u8]) -> TwoDa {
        let text = crate::text::decode_all(data);
        let split = |line: &str| -> Vec<String> {
            let mut cells = Vec::new();
            let mut chars = line.chars().peekable();
            while let Some(&c) = chars.peek() {
                if c.is_whitespace() {
                    chars.next();
                } else if c == '"' {
                    chars.next();
                    cells.push(chars.by_ref().take_while(|&c| c != '"').collect());
                } else {
                    let mut cell = String::new();
                    while let Some(&c) = chars.peek() {
                        if c.is_whitespace() {
                            break;
                        }
                        cell.push(c);
                        chars.next();
                    }
                    cells.push(cell);
                }
            }
            cells
        };
        let mut lines = text.lines().skip(1).filter(|l| !l.trim().is_empty());
        let mut header = lines.next().map(split).unwrap_or_default();
        if header.first().map_or(false, |h| h.starts_with("DEFAULT")) {
            header = lines.next().map(split).unwrap_or_default();
        }
        let columns: Vec<String> = header.iter().map(|c| c.to_ascii_lowercase()).collect();
        let mut rows = Vec::new();
        for line in lines {
            let cells = split(line);
            let mut row: Vec<String> = cells.into_iter().skip(1).collect();
            row.resize(columns.len(), String::new());
            rows.push(row);
        }
        TwoDa { columns, rows }
    }

    pub fn column(&self, name: &str) -> Option<usize> {
        self.columns.iter().position(|c| c.eq_ignore_ascii_case(name))
    }

    /// A cell, or None for "****" and missing rows and columns.
    pub fn cell(&self, row: usize, column: &str) -> Option<&str> {
        let c = self.column(column)?;
        let v = self.rows.get(row)?.get(c)?;
        if v.is_empty() || v == "****" {
            None
        } else {
            Some(v.as_str())
        }
    }

    pub fn int(&self, row: usize, column: &str) -> Option<i64> {
        let v = self.cell(row, column)?;
        if let Some(hex) = v.strip_prefix("0x") {
            i64::from_str_radix(hex, 16).ok()
        } else {
            v.parse().ok()
        }
    }
}

pub struct Tlk {
    data: Vec<u8>,
    count: usize,
    entries: usize,
}

impl Tlk {
    pub fn open(path: &Path) -> Option<Tlk> {
        let data = fs::read(path).ok()?;
        if data.get(0..8)? != b"TLK V3.0" {
            return None;
        }
        let count = u32_at(&data, 12)? as usize;
        let entries = u32_at(&data, 16)? as usize;
        Some(Tlk { data, count, entries })
    }

    pub fn get(&self, strref: u32) -> Option<String> {
        let i = strref as usize;
        if i >= self.count {
            return None;
        }
        let at = 20 + i * 40;
        let offset = u32_at(&self.data, at + 28)? as usize;
        let size = u32_at(&self.data, at + 32)? as usize;
        let start = self.entries + offset;
        let text = crate::text::decode(self.data.get(start..start + size)?);
        if text.is_empty() {
            None
        } else {
            Some(text)
        }
    }
}
