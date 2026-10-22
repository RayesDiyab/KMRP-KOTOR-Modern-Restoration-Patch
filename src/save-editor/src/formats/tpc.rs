//! TPC, the game's own texture format, for the portraits: uncompressed grey, RGB or
//! RGBA, or DXT1/DXT5 blocks, with a 128-byte header. Only the first mip level is
//! decoded. Rows are stored bottom first, as in a TGA.

use super::tga::Image;

pub fn decode(data: &[u8]) -> Option<Image> {
    if data.len() < 128 {
        return None;
    }
    let size = u32::from_le_bytes(data[0..4].try_into().ok()?) as usize;
    let w = u16::from_le_bytes([data[8], data[9]]) as usize;
    let h = u16::from_le_bytes([data[10], data[11]]) as usize;
    let encoding = data[12];
    if w == 0 || h == 0 || w > 4096 || h > 4096 {
        return None;
    }
    let body = &data[128..];
    let mut rgba = vec![0u8; w * h * 4];
    if size == 0 {
        let bpp = match encoding {
            1 => 1,
            2 => 3,
            4 => 4,
            _ => return None,
        };
        let px = body.get(..w * h * bpp)?;
        for i in 0..w * h {
            let p = &px[i * bpp..i * bpp + bpp];
            let (r, g, b, a) = match bpp {
                1 => (p[0], p[0], p[0], 255),
                3 => (p[0], p[1], p[2], 255),
                _ => (p[0], p[1], p[2], p[3]),
            };
            rgba[i * 4..i * 4 + 4].copy_from_slice(&[r, g, b, a]);
        }
    } else {
        let dxt5 = encoding == 4;
        let block = if dxt5 { 16 } else { 8 };
        let (bw, bh) = ((w + 3) / 4, (h + 3) / 4);
        let blocks = body.get(..bw * bh * block)?;
        for by in 0..bh {
            for bx in 0..bw {
                let b = &blocks[(by * bw + bx) * block..(by * bw + bx + 1) * block];
                let (alpha, colour) = if dxt5 { (Some(&b[0..8]), &b[8..16]) } else { (None, &b[0..8]) };
                let texels = decode_block(colour, alpha);
                for ty in 0..4 {
                    for tx in 0..4 {
                        let (x, y) = (bx * 4 + tx, by * 4 + ty);
                        if x < w && y < h {
                            rgba[(y * w + x) * 4..(y * w + x) * 4 + 4].copy_from_slice(&texels[ty * 4 + tx]);
                        }
                    }
                }
            }
        }
    }
    // Bottom row first in the file.
    let row = w * 4;
    let mut flipped = vec![0u8; rgba.len()];
    for y in 0..h {
        flipped[y * row..(y + 1) * row].copy_from_slice(&rgba[(h - 1 - y) * row..(h - y) * row]);
    }
    Some(Image { width: w as u32, height: h as u32, rgba: flipped })
}

fn rgb565(v: u16) -> [u8; 3] {
    let r = ((v >> 11) & 31) as u32;
    let g = ((v >> 5) & 63) as u32;
    let b = (v & 31) as u32;
    [(r * 255 / 31) as u8, (g * 255 / 63) as u8, (b * 255 / 31) as u8]
}

fn decode_block(c: &[u8], alpha: Option<&[u8]>) -> [[u8; 4]; 16] {
    let c0 = u16::from_le_bytes([c[0], c[1]]);
    let c1 = u16::from_le_bytes([c[2], c[3]]);
    let (a, b) = (rgb565(c0), rgb565(c1));
    let mix = |x: u8, y: u8, wx: u32, wy: u32| ((x as u32 * wx + y as u32 * wy) / (wx + wy)) as u8;
    let mut palette = [[0u8; 4]; 4];
    palette[0] = [a[0], a[1], a[2], 255];
    palette[1] = [b[0], b[1], b[2], 255];
    if c0 > c1 || alpha.is_some() {
        palette[2] = [mix(a[0], b[0], 2, 1), mix(a[1], b[1], 2, 1), mix(a[2], b[2], 2, 1), 255];
        palette[3] = [mix(a[0], b[0], 1, 2), mix(a[1], b[1], 1, 2), mix(a[2], b[2], 1, 2), 255];
    } else {
        palette[2] = [mix(a[0], b[0], 1, 1), mix(a[1], b[1], 1, 1), mix(a[2], b[2], 1, 1), 255];
        palette[3] = [0, 0, 0, 0];
    }
    let bits = u32::from_le_bytes([c[4], c[5], c[6], c[7]]);
    let mut out = [[0u8; 4]; 16];
    for i in 0..16 {
        out[i] = palette[((bits >> (i * 2)) & 3) as usize];
    }
    if let Some(al) = alpha {
        let (a0, a1) = (al[0] as u32, al[1] as u32);
        let mut levels = [0u32; 8];
        levels[0] = a0;
        levels[1] = a1;
        if a0 > a1 {
            for i in 1..7 {
                levels[i + 1] = ((7 - i as u32) * a0 + i as u32 * a1) / 7;
            }
        } else {
            for i in 1..5 {
                levels[i + 1] = ((5 - i as u32) * a0 + i as u32 * a1) / 5;
            }
            levels[6] = 0;
            levels[7] = 255;
        }
        let mut abits: u64 = 0;
        for (i, &byte) in al[2..8].iter().enumerate() {
            abits |= (byte as u64) << (8 * i);
        }
        for i in 0..16 {
            out[i][3] = levels[((abits >> (i * 3)) & 7) as usize] as u8;
        }
    }
    out
}
