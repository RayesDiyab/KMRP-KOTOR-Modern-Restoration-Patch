//! Screen.tga, the picture a save shows in the game's Load screen: uncompressed or RLE
//! truecolour, 24 or 32 bits. Decoded to RGBA, top row first.

pub struct Image {
    pub width: u32,
    pub height: u32,
    pub rgba: Vec<u8>,
}

pub fn decode(data: &[u8]) -> Option<Image> {
    if data.len() < 18 {
        return None;
    }
    let id_len = data[0] as usize;
    let kind = data[2];
    let width = u16::from_le_bytes([data[12], data[13]]) as u32;
    let height = u16::from_le_bytes([data[14], data[15]]) as u32;
    let bpp = data[16] as usize;
    let top_first = data[17] & 0x20 != 0;
    if !(kind == 2 || kind == 10) || !(bpp == 24 || bpp == 32) || width == 0 || height == 0 {
        return None;
    }
    let colormap = if data[1] != 0 {
        u16::from_le_bytes([data[5], data[6]]) as usize * ((data[7] as usize + 7) / 8)
    } else {
        0
    };
    let mut pos = 18 + id_len + colormap;
    let px = bpp / 8;
    let total = (width * height) as usize;
    let mut pixels: Vec<[u8; 4]> = Vec::with_capacity(total);
    let read = |at: usize| -> Option<[u8; 4]> {
        let p = data.get(at..at + px)?;
        Some([p[2], p[1], p[0], if px == 4 { p[3] } else { 255 }])
    };
    if kind == 2 {
        for i in 0..total {
            pixels.push(read(pos + i * px)?);
        }
    } else {
        while pixels.len() < total {
            let head = *data.get(pos)?;
            pos += 1;
            let n = (head & 0x7F) as usize + 1;
            if head & 0x80 != 0 {
                let p = read(pos)?;
                pos += px;
                pixels.extend(std::iter::repeat(p).take(n));
            } else {
                for _ in 0..n {
                    pixels.push(read(pos)?);
                    pos += px;
                }
            }
        }
        pixels.truncate(total);
    }
    let mut rgba = Vec::with_capacity(total * 4);
    for y in 0..height as usize {
        let row = if top_first { y } else { height as usize - 1 - y };
        for x in 0..width as usize {
            let mut p = pixels[row * width as usize + x];
            // The game's screenshots carry no real alpha.
            p[3] = 255;
            rgba.extend_from_slice(&p);
        }
    }
    Some(Image { width, height, rgba })
}
