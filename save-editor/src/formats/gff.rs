//! GFF V3.2, BioWare's generic file format: every .res, .utc, .uti, .ifo and .git in a
//! save. Read into a tree and written back from it. Strings stay as the bytes the game
//! wrote (Windows-1252 for the Western releases), so nothing is lost on a round trip.

use std::fmt;

#[derive(Debug)]
pub struct GffError(pub String);

impl fmt::Display for GffError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl std::error::Error for GffError {}

fn err<T>(message: impl Into<String>) -> Result<T, GffError> {
    Err(GffError(message.into()))
}

#[derive(Clone, Debug, PartialEq)]
pub struct LocString {
    pub strref: u32,
    /// (language id * 2 + gender, text bytes)
    pub strings: Vec<(u32, Vec<u8>)>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Byte(u8),
    Char(i8),
    Word(u16),
    Short(i16),
    Dword(u32),
    Int(i32),
    Dword64(u64),
    Int64(i64),
    Float(f32),
    Double(f64),
    String(Vec<u8>),
    ResRef(Vec<u8>),
    LocString(LocString),
    Void(Vec<u8>),
    Struct(Struct),
    List(Vec<Struct>),
    Orientation([f32; 4]),
    Vector([f32; 3]),
}

impl Value {
    fn type_id(&self) -> u32 {
        match self {
            Value::Byte(_) => 0,
            Value::Char(_) => 1,
            Value::Word(_) => 2,
            Value::Short(_) => 3,
            Value::Dword(_) => 4,
            Value::Int(_) => 5,
            Value::Dword64(_) => 6,
            Value::Int64(_) => 7,
            Value::Float(_) => 8,
            Value::Double(_) => 9,
            Value::String(_) => 10,
            Value::ResRef(_) => 11,
            Value::LocString(_) => 12,
            Value::Void(_) => 13,
            Value::Struct(_) => 14,
            Value::List(_) => 15,
            Value::Orientation(_) => 16,
            Value::Vector(_) => 17,
        }
    }

    /// Any whole-number field as an i64, whatever its width.
    pub fn as_int(&self) -> Option<i64> {
        Some(match *self {
            Value::Byte(v) => v as i64,
            Value::Char(v) => v as i64,
            Value::Word(v) => v as i64,
            Value::Short(v) => v as i64,
            Value::Dword(v) => v as i64,
            Value::Int(v) => v as i64,
            Value::Dword64(v) => v as i64,
            Value::Int64(v) => v,
            _ => return None,
        })
    }

    /// The same field type holding `value`, clamped to what the type can hold.
    pub fn with_int(&self, value: i64) -> Option<Value> {
        fn clamp(v: i64, lo: i64, hi: i64) -> i64 {
            v.max(lo).min(hi)
        }
        Some(match self {
            Value::Byte(_) => Value::Byte(clamp(value, 0, u8::MAX as i64) as u8),
            Value::Char(_) => Value::Char(clamp(value, i8::MIN as i64, i8::MAX as i64) as i8),
            Value::Word(_) => Value::Word(clamp(value, 0, u16::MAX as i64) as u16),
            Value::Short(_) => Value::Short(clamp(value, i16::MIN as i64, i16::MAX as i64) as i16),
            Value::Dword(_) => Value::Dword(clamp(value, 0, u32::MAX as i64) as u32),
            Value::Int(_) => Value::Int(clamp(value, i32::MIN as i64, i32::MAX as i64) as i32),
            Value::Dword64(_) => Value::Dword64(value.max(0) as u64),
            Value::Int64(_) => Value::Int64(value),
            _ => return None,
        })
    }
}

#[derive(Clone, Debug, PartialEq, Default)]
pub struct Struct {
    pub id: u32,
    pub fields: Vec<(String, Value)>,
}

impl Struct {
    pub fn new(id: u32) -> Struct {
        Struct { id, fields: Vec::new() }
    }

    pub fn get(&self, label: &str) -> Option<&Value> {
        self.fields.iter().find(|(l, _)| l == label).map(|(_, v)| v)
    }

    pub fn get_mut(&mut self, label: &str) -> Option<&mut Value> {
        self.fields.iter_mut().find(|(l, _)| l == label).map(|(_, v)| v)
    }

    pub fn int(&self, label: &str) -> Option<i64> {
        self.get(label).and_then(Value::as_int)
    }

    pub fn float(&self, label: &str) -> Option<f32> {
        match self.get(label)? {
            Value::Float(v) => Some(*v),
            _ => None,
        }
    }

    pub fn string(&self, label: &str) -> Option<String> {
        match self.get(label)? {
            Value::String(b) | Value::ResRef(b) => Some(crate::text::decode(b)),
            _ => None,
        }
    }

    pub fn list(&self, label: &str) -> Option<&Vec<Struct>> {
        match self.get(label)? {
            Value::List(l) => Some(l),
            _ => None,
        }
    }

    pub fn list_mut(&mut self, label: &str) -> Option<&mut Vec<Struct>> {
        match self.get_mut(label)? {
            Value::List(l) => Some(l),
            _ => None,
        }
    }

    pub fn child(&self, label: &str) -> Option<&Struct> {
        match self.get(label)? {
            Value::Struct(s) => Some(s),
            _ => None,
        }
    }

    pub fn child_mut(&mut self, label: &str) -> Option<&mut Struct> {
        match self.get_mut(label)? {
            Value::Struct(s) => Some(s),
            _ => None,
        }
    }

    /// Sets a whole-number field, keeping the type the game gave it. A missing field is
    /// added with `fallback`'s type. Returns false if the field is not a number.
    pub fn set_int(&mut self, label: &str, value: i64, fallback: Value) -> bool {
        match self.get_mut(label) {
            Some(existing) => match existing.with_int(value) {
                Some(v) => {
                    *existing = v;
                    true
                }
                None => false,
            },
            None => match fallback.with_int(value) {
                Some(v) => {
                    self.fields.push((label.to_string(), v));
                    true
                }
                None => false,
            },
        }
    }

    pub fn set(&mut self, label: &str, value: Value) {
        match self.get_mut(label) {
            Some(existing) => *existing = value,
            None => self.fields.push((label.to_string(), value)),
        }
    }

    pub fn set_float(&mut self, label: &str, value: f32) {
        self.set(label, Value::Float(value));
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Gff {
    /// "UTC ", "IFO ", "GIT ", "RES ", "NFO ", "PT  ", "GVT ", "INV " ...
    pub file_type: [u8; 4],
    pub root: Struct,
}

struct Reader<'a> {
    data: &'a [u8],
    struct_offset: usize,
    struct_count: usize,
    field_offset: usize,
    field_count: usize,
    label_offset: usize,
    label_count: usize,
    field_data_offset: usize,
    field_data_len: usize,
    field_indices_offset: usize,
    field_indices_len: usize,
    list_indices_offset: usize,
    list_indices_len: usize,
    depth: usize,
}

fn u32_at(data: &[u8], at: usize) -> Result<u32, GffError> {
    data.get(at..at + 4)
        .map(|b| u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
        .ok_or_else(|| GffError(format!("read past the end at {}", at)))
}

impl<'a> Reader<'a> {
    fn bytes(&self, at: usize, len: usize) -> Result<&'a [u8], GffError> {
        self.data
            .get(at..at.checked_add(len).ok_or_else(|| GffError("length overflow".into()))?)
            .ok_or_else(|| GffError(format!("{} bytes at {} run past the end", len, at)))
    }

    fn field_data(&self, offset: u32, len: usize) -> Result<&'a [u8], GffError> {
        let offset = offset as usize;
        if offset.checked_add(len).map_or(true, |end| end > self.field_data_len) {
            return err(format!("field data at {} runs past its block", offset));
        }
        self.bytes(self.field_data_offset + offset, len)
    }

    fn label(&self, index: u32) -> Result<String, GffError> {
        let index = index as usize;
        if index >= self.label_count {
            return err(format!("label {} out of range", index));
        }
        let raw = self.bytes(self.label_offset + index * 16, 16)?;
        let end = raw.iter().position(|&b| b == 0).unwrap_or(16);
        Ok(raw[..end].iter().map(|&b| b as char).collect())
    }

    fn read_struct(&mut self, index: u32) -> Result<Struct, GffError> {
        let index = index as usize;
        if index >= self.struct_count {
            return err(format!("struct {} out of range", index));
        }
        self.depth += 1;
        if self.depth > 64 {
            return err("structs nested too deeply");
        }
        let at = self.struct_offset + index * 12;
        let id = u32_at(self.data, at)?;
        let data = u32_at(self.data, at + 4)?;
        let count = u32_at(self.data, at + 8)? as usize;
        let mut s = Struct::new(id);
        if count == 1 {
            let (label, value) = self.read_field(data)?;
            s.fields.push((label, value));
        } else if count > 1 {
            let start = data as usize;
            if start + count * 4 > self.field_indices_len {
                return err("field indices run past their block");
            }
            for i in 0..count {
                let field = u32_at(self.data, self.field_indices_offset + start + i * 4)?;
                let (label, value) = self.read_field(field)?;
                s.fields.push((label, value));
            }
        }
        self.depth -= 1;
        Ok(s)
    }

    fn read_field(&mut self, index: u32) -> Result<(String, Value), GffError> {
        let index = index as usize;
        if index >= self.field_count {
            return err(format!("field {} out of range", index));
        }
        let at = self.field_offset + index * 12;
        let kind = u32_at(self.data, at)?;
        let label = self.label(u32_at(self.data, at + 4)?)?;
        let raw = self.bytes(at + 8, 4)?;
        let data = u32::from_le_bytes([raw[0], raw[1], raw[2], raw[3]]);
        let value = match kind {
            0 => Value::Byte(raw[0]),
            1 => Value::Char(raw[0] as i8),
            2 => Value::Word(u16::from_le_bytes([raw[0], raw[1]])),
            3 => Value::Short(i16::from_le_bytes([raw[0], raw[1]])),
            4 => Value::Dword(data),
            5 => Value::Int(data as i32),
            6 => Value::Dword64(u64::from_le_bytes(self.field_data(data, 8)?.try_into().unwrap())),
            7 => Value::Int64(i64::from_le_bytes(self.field_data(data, 8)?.try_into().unwrap())),
            8 => Value::Float(f32::from_le_bytes([raw[0], raw[1], raw[2], raw[3]])),
            9 => Value::Double(f64::from_le_bytes(self.field_data(data, 8)?.try_into().unwrap())),
            10 => {
                let len = u32::from_le_bytes(self.field_data(data, 4)?.try_into().unwrap()) as usize;
                Value::String(self.field_data(data + 4, len)?.to_vec())
            }
            11 => {
                let len = self.field_data(data, 1)?[0] as usize;
                Value::ResRef(self.field_data(data + 1, len)?.to_vec())
            }
            12 => {
                let head = self.field_data(data, 12)?;
                let strref = u32::from_le_bytes(head[4..8].try_into().unwrap());
                let count = u32::from_le_bytes(head[8..12].try_into().unwrap()) as usize;
                let mut strings = Vec::new();
                let mut pos = data + 12;
                for _ in 0..count.min(64) {
                    let entry = self.field_data(pos, 8)?;
                    let id = u32::from_le_bytes(entry[0..4].try_into().unwrap());
                    let len = u32::from_le_bytes(entry[4..8].try_into().unwrap());
                    strings.push((id, self.field_data(pos + 8, len as usize)?.to_vec()));
                    pos += 8 + len;
                }
                Value::LocString(LocString { strref, strings })
            }
            13 => {
                let len = u32::from_le_bytes(self.field_data(data, 4)?.try_into().unwrap()) as usize;
                Value::Void(self.field_data(data + 4, len)?.to_vec())
            }
            14 => Value::Struct(self.read_struct(data)?),
            15 => {
                let start = data as usize;
                if start + 4 > self.list_indices_len {
                    return err("list runs past its block");
                }
                let count = u32_at(self.data, self.list_indices_offset + start)? as usize;
                if start + 4 + count * 4 > self.list_indices_len {
                    return err("list runs past its block");
                }
                let mut items = Vec::with_capacity(count);
                for i in 0..count {
                    let s = u32_at(self.data, self.list_indices_offset + start + 4 + i * 4)?;
                    items.push(self.read_struct(s)?);
                }
                Value::List(items)
            }
            16 => {
                let b = self.field_data(data, 16)?;
                Value::Orientation(std::array::from_fn(|i| f32::from_le_bytes(b[i * 4..i * 4 + 4].try_into().unwrap())))
            }
            17 => {
                let b = self.field_data(data, 12)?;
                Value::Vector(std::array::from_fn(|i| f32::from_le_bytes(b[i * 4..i * 4 + 4].try_into().unwrap())))
            }
            other => return err(format!("unknown field type {} for {}", other, label)),
        };
        Ok((label, value))
    }
}

impl Gff {
    pub fn read(data: &[u8]) -> Result<Gff, GffError> {
        if data.len() < 56 {
            return err("too short for a GFF header");
        }
        if &data[4..8] != b"V3.2" {
            return err("not a GFF V3.2 file");
        }
        let h = |i: usize| u32_at(data, 8 + i * 4).map(|v| v as usize);
        let mut reader = Reader {
            data,
            struct_offset: h(0)?,
            struct_count: h(1)?,
            field_offset: h(2)?,
            field_count: h(3)?,
            label_offset: h(4)?,
            label_count: h(5)?,
            field_data_offset: h(6)?,
            field_data_len: h(7)?,
            field_indices_offset: h(8)?,
            field_indices_len: h(9)?,
            list_indices_offset: h(10)?,
            list_indices_len: h(11)?,
            depth: 0,
        };
        let blocks = [
            (reader.struct_offset, reader.struct_count * 12),
            (reader.field_offset, reader.field_count * 12),
            (reader.label_offset, reader.label_count * 16),
            (reader.field_data_offset, reader.field_data_len),
            (reader.field_indices_offset, reader.field_indices_len),
            (reader.list_indices_offset, reader.list_indices_len),
        ];
        for (offset, len) in blocks {
            if offset.checked_add(len).map_or(true, |end| end > data.len()) {
                return err("a GFF block runs past the end of the file");
            }
        }
        if reader.struct_count == 0 {
            return err("GFF has no root struct");
        }
        let root = reader.read_struct(0)?;
        Ok(Gff { file_type: data[0..4].try_into().unwrap(), root })
    }

    pub fn write(&self) -> Vec<u8> {
        let mut w = Writer::default();
        w.structs.push([0; 3]);
        w.fill_struct(0, &self.root);
        let mut out = Vec::new();
        let header_len = 56usize;
        let struct_bytes = w.structs.len() * 12;
        let field_bytes = w.fields.len() * 12;
        let label_bytes = w.labels.len() * 16;
        let mut offset = header_len;
        let mut header = Vec::with_capacity(56);
        header.extend_from_slice(&self.file_type);
        header.extend_from_slice(b"V3.2");
        for (len, count) in [
            (struct_bytes, w.structs.len()),
            (field_bytes, w.fields.len()),
            (label_bytes, w.labels.len()),
            (w.field_data.len(), w.field_data.len()),
            (w.field_indices.len(), w.field_indices.len()),
            (w.list_indices.len(), w.list_indices.len()),
        ] {
            header.extend_from_slice(&(offset as u32).to_le_bytes());
            header.extend_from_slice(&(count as u32).to_le_bytes());
            offset += len;
        }
        out.extend_from_slice(&header);
        for s in &w.structs {
            for v in s {
                out.extend_from_slice(&v.to_le_bytes());
            }
        }
        for f in &w.fields {
            for v in f {
                out.extend_from_slice(&v.to_le_bytes());
            }
        }
        for label in &w.labels {
            let mut raw = [0u8; 16];
            for (i, b) in label.bytes().take(16).enumerate() {
                raw[i] = b;
            }
            out.extend_from_slice(&raw);
        }
        out.extend_from_slice(&w.field_data);
        out.extend_from_slice(&w.field_indices);
        out.extend_from_slice(&w.list_indices);
        out
    }
}

#[derive(Default)]
struct Writer {
    structs: Vec<[u32; 3]>,
    fields: Vec<[u32; 3]>,
    labels: Vec<String>,
    field_data: Vec<u8>,
    field_indices: Vec<u8>,
    list_indices: Vec<u8>,
}

impl Writer {
    fn label(&mut self, label: &str) -> u32 {
        if let Some(i) = self.labels.iter().position(|l| l == label) {
            return i as u32;
        }
        self.labels.push(label.to_string());
        (self.labels.len() - 1) as u32
    }

    fn data(&mut self, bytes: &[u8]) -> u32 {
        let at = self.field_data.len() as u32;
        self.field_data.extend_from_slice(bytes);
        at
    }

    /// Fills the already reserved struct slot `index` with `s` and its fields.
    fn fill_struct(&mut self, index: usize, s: &Struct) {
        let fields: Vec<u32> = s.fields.iter().map(|(l, v)| self.add_field(l, v)).collect();
        let data = match fields.len() {
            0 => u32::MAX,
            1 => fields[0],
            _ => {
                let at = self.field_indices.len() as u32;
                for f in &fields {
                    self.field_indices.extend_from_slice(&f.to_le_bytes());
                }
                at
            }
        };
        self.structs[index] = [s.id, data, fields.len() as u32];
    }

    fn new_struct(&mut self, s: &Struct) -> u32 {
        let index = self.structs.len();
        self.structs.push([0; 3]);
        self.fill_struct(index, s);
        index as u32
    }

    fn add_field(&mut self, label: &str, value: &Value) -> u32 {
        let index = self.fields.len();
        self.fields.push([0; 3]);
        let label = self.label(label);
        let data = match value {
            Value::Byte(v) => *v as u32,
            Value::Char(v) => *v as u8 as u32,
            Value::Word(v) => *v as u32,
            Value::Short(v) => *v as u16 as u32,
            Value::Dword(v) => *v,
            Value::Int(v) => *v as u32,
            Value::Float(v) => v.to_bits(),
            Value::Dword64(v) => self.data(&v.to_le_bytes()),
            Value::Int64(v) => self.data(&v.to_le_bytes()),
            Value::Double(v) => self.data(&v.to_le_bytes()),
            Value::String(b) => {
                let at = self.data(&(b.len() as u32).to_le_bytes());
                self.data(b);
                at
            }
            Value::ResRef(b) => {
                let len = b.len().min(255);
                let at = self.data(&[len as u8]);
                self.data(&b[..len]);
                at
            }
            Value::LocString(l) => {
                let mut body = Vec::new();
                body.extend_from_slice(&l.strref.to_le_bytes());
                body.extend_from_slice(&(l.strings.len() as u32).to_le_bytes());
                for (id, text) in &l.strings {
                    body.extend_from_slice(&id.to_le_bytes());
                    body.extend_from_slice(&(text.len() as u32).to_le_bytes());
                    body.extend_from_slice(text);
                }
                let at = self.data(&(body.len() as u32).to_le_bytes());
                self.data(&body);
                at
            }
            Value::Void(b) => {
                let at = self.data(&(b.len() as u32).to_le_bytes());
                self.data(b);
                at
            }
            Value::Struct(s) => self.new_struct(s),
            Value::List(items) => {
                // Reserve the list's slot first, then its structs' indices.
                let at = self.list_indices.len();
                self.list_indices.extend(std::iter::repeat(0).take(4 + items.len() * 4));
                self.list_indices[at..at + 4].copy_from_slice(&(items.len() as u32).to_le_bytes());
                for (i, item) in items.iter().enumerate() {
                    let s = self.new_struct(item);
                    let p = at + 4 + i * 4;
                    self.list_indices[p..p + 4].copy_from_slice(&s.to_le_bytes());
                }
                at as u32
            }
            Value::Orientation(q) => {
                let bytes: Vec<u8> = q.iter().flat_map(|f| f.to_le_bytes()).collect();
                self.data(&bytes)
            }
            Value::Vector(v) => {
                let bytes: Vec<u8> = v.iter().flat_map(|f| f.to_le_bytes()).collect();
                self.data(&bytes)
            }
        };
        self.fields[index] = [value.type_id(), label, data];
        index as u32
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip() {
        let mut root = Struct::new(u32::MAX);
        root.fields.push(("Credits".into(), Value::Dword(1234)));
        root.fields.push(("Name".into(), Value::String(b"Revan".to_vec())));
        let mut item = Struct::new(0);
        item.fields.push(("Tag".into(), Value::ResRef(b"g_w_lghtsbr01".to_vec())));
        item.fields.push(("Stack".into(), Value::Word(3)));
        root.fields.push(("ItemList".into(), Value::List(vec![item.clone(), item])));
        root.fields.push(("Pos".into(), Value::Vector([1.0, 2.0, 3.0])));
        root.fields.push((
            "FirstName".into(),
            Value::LocString(LocString { strref: u32::MAX, strings: vec![(0, b"Bastila".to_vec())] }),
        ));
        let gff = Gff { file_type: *b"RES ", root };
        let bytes = gff.write();
        assert_eq!(Gff::read(&bytes).unwrap(), gff);
    }
}
