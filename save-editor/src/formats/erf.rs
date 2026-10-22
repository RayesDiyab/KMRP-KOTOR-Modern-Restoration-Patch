//! ERF V1.0 archives: "MOD " (a save's SAVEGAME.sav and each module's .sav inside it),
//! "ERF " and "SAV ". Read whole into memory (a save is a few megabytes) and written
//! back with the same header fields, resources in the same order.

use super::gff::GffError;

pub const RES_TYPE_SAV: u16 = 2057;
pub const RES_TYPE_IFO: u16 = 2014;
pub const RES_TYPE_GIT: u16 = 2023;
pub const RES_TYPE_UTC: u16 = 2027;
pub const RES_TYPE_UTI: u16 = 2025;
pub const RES_TYPE_RES: u16 = 0;
pub const RES_TYPE_2DA: u16 = 2017;
pub const RES_TYPE_TGA: u16 = 3;
pub const RES_TYPE_TPC: u16 = 3007;
pub const RES_TYPE_ARE: u16 = 2012;

#[derive(Clone, Debug, PartialEq)]
pub struct Resource {
    pub name: String,
    pub kind: u16,
    pub id: u32,
    pub data: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Erf {
    pub file_type: [u8; 4],
    pub version: [u8; 4],
    /// Raw localized-string block, kept as it was.
    pub language_count: u32,
    pub localized: Vec<u8>,
    pub build_year: u32,
    pub build_day: u32,
    pub description_strref: u32,
    pub reserved: Vec<u8>,
    pub resources: Vec<Resource>,
}

fn u32_at(data: &[u8], at: usize) -> Result<u32, GffError> {
    data.get(at..at + 4)
        .map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .ok_or_else(|| GffError(format!("archive read past the end at {}", at)))
}

impl Erf {
    pub fn read(data: &[u8]) -> Result<Erf, GffError> {
        if data.len() < 160 || &data[4..8] != b"V1.0" {
            return Err(GffError("not an ERF V1.0 archive".into()));
        }
        let language_count = u32_at(data, 8)?;
        let localized_size = u32_at(data, 12)? as usize;
        let count = u32_at(data, 16)? as usize;
        let localized_offset = u32_at(data, 20)? as usize;
        let keys = u32_at(data, 24)? as usize;
        let list = u32_at(data, 28)? as usize;
        let localized = data
            .get(localized_offset..localized_offset + localized_size)
            .unwrap_or(&[])
            .to_vec();
        let mut resources = Vec::with_capacity(count);
        for i in 0..count {
            let key = data
                .get(keys + i * 24..keys + i * 24 + 24)
                .ok_or_else(|| GffError("archive key list runs past the end".into()))?;
            let end = key[..16].iter().position(|&b| b == 0).unwrap_or(16);
            let name: String = key[..end].iter().map(|&b| b as char).collect();
            let id = u32::from_le_bytes(key[16..20].try_into().unwrap());
            let kind = u16::from_le_bytes(key[20..22].try_into().unwrap());
            let offset = u32_at(data, list + i * 8)? as usize;
            let size = u32_at(data, list + i * 8 + 4)? as usize;
            let body = data
                .get(offset..offset.saturating_add(size))
                .ok_or_else(|| GffError(format!("{} runs past the end of the archive", name)))?;
            resources.push(Resource { name, kind, id, data: body.to_vec() });
        }
        Ok(Erf {
            file_type: data[0..4].try_into().unwrap(),
            version: data[4..8].try_into().unwrap(),
            language_count,
            localized,
            build_year: u32_at(data, 32)?,
            build_day: u32_at(data, 36)?,
            description_strref: u32_at(data, 40)?,
            reserved: data[44..160].to_vec(),
            resources,
        })
    }

    pub fn write(&self) -> Vec<u8> {
        let count = self.resources.len();
        let localized_offset = 160usize;
        let keys = localized_offset + self.localized.len();
        let list = keys + count * 24;
        let mut offset = list + count * 8;
        let mut out = Vec::with_capacity(offset + self.resources.iter().map(|r| r.data.len()).sum::<usize>());
        out.extend_from_slice(&self.file_type);
        out.extend_from_slice(&self.version);
        for v in [
            self.language_count,
            self.localized.len() as u32,
            count as u32,
            localized_offset as u32,
            keys as u32,
            list as u32,
            self.build_year,
            self.build_day,
            self.description_strref,
        ] {
            out.extend_from_slice(&v.to_le_bytes());
        }
        let mut reserved = self.reserved.clone();
        reserved.resize(116, 0);
        out.extend_from_slice(&reserved);
        out.extend_from_slice(&self.localized);
        for (i, r) in self.resources.iter().enumerate() {
            let mut name = [0u8; 16];
            for (j, b) in r.name.bytes().take(16).enumerate() {
                name[j] = b;
            }
            out.extend_from_slice(&name);
            out.extend_from_slice(&(i as u32).to_le_bytes());
            out.extend_from_slice(&r.kind.to_le_bytes());
            out.extend_from_slice(&[0, 0]);
        }
        for r in &self.resources {
            out.extend_from_slice(&(offset as u32).to_le_bytes());
            out.extend_from_slice(&(r.data.len() as u32).to_le_bytes());
            offset += r.data.len();
        }
        for r in &self.resources {
            out.extend_from_slice(&r.data);
        }
        out
    }

    pub fn find(&self, name: &str, kind: u16) -> Option<&Resource> {
        self.resources.iter().find(|r| r.kind == kind && r.name.eq_ignore_ascii_case(name))
    }

    pub fn find_mut(&mut self, name: &str, kind: u16) -> Option<&mut Resource> {
        self.resources.iter_mut().find(|r| r.kind == kind && r.name.eq_ignore_ascii_case(name))
    }
}

/// An archive's table of contents, read without its contents: for the game's texture
/// packs (the GUI pack alone is over 100 MB), whose resources are read one at a time.
pub struct ErfIndex {
    path: std::path::PathBuf,
    entries: std::collections::HashMap<(String, u16), (u32, u32)>,
}

impl ErfIndex {
    pub fn open(path: &std::path::Path) -> Option<ErfIndex> {
        use std::io::{Read, Seek, SeekFrom};
        let mut file = std::fs::File::open(path).ok()?;
        let mut head = [0u8; 160];
        file.read_exact(&mut head).ok()?;
        if &head[4..8] != b"V1.0" {
            return None;
        }
        let count = u32::from_le_bytes(head[16..20].try_into().ok()?) as usize;
        let keys = u32::from_le_bytes(head[24..28].try_into().ok()?) as u64;
        let list = u32::from_le_bytes(head[28..32].try_into().ok()?) as u64;
        let mut key_raw = vec![0u8; count * 24];
        file.seek(SeekFrom::Start(keys)).ok()?;
        file.read_exact(&mut key_raw).ok()?;
        let mut list_raw = vec![0u8; count * 8];
        file.seek(SeekFrom::Start(list)).ok()?;
        file.read_exact(&mut list_raw).ok()?;
        let mut entries = std::collections::HashMap::with_capacity(count);
        for i in 0..count {
            let k = &key_raw[i * 24..i * 24 + 24];
            let end = k[..16].iter().position(|&b| b == 0).unwrap_or(16);
            let name: String = k[..end].iter().map(|&b| (b as char).to_ascii_lowercase()).collect();
            let kind = u16::from_le_bytes([k[20], k[21]]);
            let offset = u32::from_le_bytes(list_raw[i * 8..i * 8 + 4].try_into().ok()?);
            let size = u32::from_le_bytes(list_raw[i * 8 + 4..i * 8 + 8].try_into().ok()?);
            entries.insert((name, kind), (offset, size));
        }
        Some(ErfIndex { path: path.to_path_buf(), entries })
    }

    pub fn read(&self, name: &str, kind: u16) -> Option<Vec<u8>> {
        let (offset, size) = *self.entries.get(&(name.to_ascii_lowercase(), kind))?;
        crate::formats::tables::read_at(&self.path, offset as u64, size as usize)
    }
}
