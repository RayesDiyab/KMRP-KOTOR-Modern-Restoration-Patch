//! RIM V1.0, the game's module archives (modules/<module>.rim and <module>_s.rim): a
//! table of resources read without their contents, each read from the file on demand.

use std::collections::HashMap;
use std::io::{Read, Seek, SeekFrom};
use std::path::{Path, PathBuf};

pub struct Rim {
    path: PathBuf,
    entries: HashMap<(String, u16), (u32, u32)>,
}

impl Rim {
    pub fn open(path: &Path) -> Option<Rim> {
        let mut file = std::fs::File::open(path).ok()?;
        let mut head = [0u8; 24];
        file.read_exact(&mut head).ok()?;
        if &head[0..8] != b"RIM V1.0" {
            return None;
        }
        let count = u32::from_le_bytes(head[12..16].try_into().ok()?) as usize;
        let mut keys = u32::from_le_bytes(head[16..20].try_into().ok()?) as u64;
        if keys == 0 {
            keys = 120;
        }
        let mut raw = vec![0u8; count * 32];
        file.seek(SeekFrom::Start(keys)).ok()?;
        file.read_exact(&mut raw).ok()?;
        let mut entries = HashMap::with_capacity(count);
        for i in 0..count {
            let k = &raw[i * 32..i * 32 + 32];
            let end = k[..16].iter().position(|&b| b == 0).unwrap_or(16);
            let name: String = k[..end].iter().map(|&b| (b as char).to_ascii_lowercase()).collect();
            let kind = u32::from_le_bytes(k[16..20].try_into().ok()?) as u16;
            let offset = u32::from_le_bytes(k[24..28].try_into().ok()?);
            let size = u32::from_le_bytes(k[28..32].try_into().ok()?);
            entries.insert((name, kind), (offset, size));
        }
        Some(Rim { path: path.to_path_buf(), entries })
    }

    pub fn read(&self, name: &str, kind: u16) -> Option<Vec<u8>> {
        let (offset, size) = *self.entries.get(&(name.to_ascii_lowercase(), kind))?;
        crate::formats::tables::read_at(&self.path, offset as u64, size as usize)
    }

    pub fn names(&self, kind: u16) -> Vec<String> {
        self.entries.keys().filter(|(_, k)| *k == kind).map(|(n, _)| n.clone()).collect()
    }

    pub fn kinds(&self) -> Vec<(String, u16)> {
        self.entries.keys().cloned().collect()
    }
}
