//! The games store text as Windows-1252 (the Western releases). Decoded for the screen
//! and encoded back when the player types a name; anything outside the code page
//! becomes '?', as the game would draw it.

const HIGH: [char; 32] = [
    '\u{20AC}', '\u{81}', '\u{201A}', '\u{0192}', '\u{201E}', '\u{2026}', '\u{2020}', '\u{2021}',
    '\u{02C6}', '\u{2030}', '\u{0160}', '\u{2039}', '\u{0152}', '\u{8D}', '\u{017D}', '\u{8F}',
    '\u{90}', '\u{2018}', '\u{2019}', '\u{201C}', '\u{201D}', '\u{2022}', '\u{2013}', '\u{2014}',
    '\u{02DC}', '\u{2122}', '\u{0161}', '\u{203A}', '\u{0153}', '\u{9D}', '\u{017E}', '\u{0178}',
];

pub fn decode(bytes: &[u8]) -> String {
    bytes
        .iter()
        .take_while(|&&b| b != 0)
        .map(|&b| match b {
            0x80..=0x9F => HIGH[(b - 0x80) as usize],
            _ => b as char,
        })
        .collect()
}

/// Like `decode`, but keeps going past NUL bytes (whole text files).
pub fn decode_all(bytes: &[u8]) -> String {
    bytes
        .split(|&b| b == 0)
        .map(decode)
        .collect::<Vec<_>>()
        .join("")
}

/// Without the {...} spans the game keeps in some names and hides on screen
/// ("{06}Vibrosword", "{color 02}Crystal, Green"), and the <...> tokens the game fills in
/// at run time ("<FullName> Kristall").
pub fn strip_codes(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut depth = 0;
    for c in text.chars() {
        match c {
            '{' | '<' => depth += 1,
            '}' | '>' if depth > 0 => depth -= 1,
            _ if depth == 0 => out.push(c),
            _ => {}
        }
    }
    out.trim().to_string()
}

pub fn encode(text: &str) -> Vec<u8> {
    text.chars()
        .map(|c| match c as u32 {
            0..=0x7F | 0xA0..=0xFF => c as u8,
            _ => HIGH.iter().position(|&h| h == c).map(|i| 0x80 + i as u8).unwrap_or(b'?'),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    #[test]
    fn round_trip() {
        let s = "Carth Onasi \u{2019}s \u{20AC}5 \u{e9}";
        assert_eq!(super::decode(&super::encode(s)), s);
    }
}
