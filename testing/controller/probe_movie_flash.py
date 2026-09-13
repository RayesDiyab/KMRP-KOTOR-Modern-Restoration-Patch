#!/usr/bin/env python3
"""Measure the grey flash at either end of a movie: its colour, where, how long.

Three attempts have now been made at this flash and the first two were wrong
because they were reasoned about rather than measured. What a fix needs to know
is not available by reading the disassembly:

  * the flash's actual RGB, which names its source -- 0xF0F0F0 is COLOR_BTNFACE,
    0x808080 is GRAY_BRUSH, 0xC0C0C0 is the classic 3D face, and anything else
    is a surface nobody painted rather than a brush;
  * whether it covers the whole screen or only the bars beside the picture,
    which says whether it is the movie window or something behind it;
  * how long it lasts, which separates one unpainted frame from a mode change.

Sampling speed is the whole difficulty. A full-screen `ImageGrab` of a 3440x1440
display runs at about 11/s, and even a thin band through PIL only reaches 20/s --
enough to miss the event entirely. This goes straight to GDI instead: one DC and
one DIB section created once, then a `BitBlt` of a single thin band per sample.
That runs two orders of magnitude faster and keeps the horizontal profile, so
the left bar, the picture and the right bar are all in every sample.

Usage:
    python testing/controller/probe_movie_flash.py [--seconds 45] [--band-y 700]

Start it, then play a movie. It prints a timeline of every colour change it saw.

Documentation standard: see `docs/documentation-standard.md`.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import pathlib
import struct
import tempfile
import time
import zlib

import numpy as np

SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0

gdi32 = ctypes.windll.gdi32
user32 = ctypes.windll.user32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD),
                ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class BandGrabber:
    """One reusable DC and DIB section; BitBlt a band out of the screen."""

    def __init__(self, x: int, y: int, width: int, height: int):
        self.x, self.y, self.width, self.height = x, y, width, height
        self.screen_dc = user32.GetDC(0)
        self.memory_dc = gdi32.CreateCompatibleDC(self.screen_dc)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height          # top-down
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        self.bits = ctypes.c_void_p()
        self.bitmap = gdi32.CreateDIBSection(
            self.memory_dc, ctypes.byref(info), DIB_RGB_COLORS,
            ctypes.byref(self.bits), None, 0)
        gdi32.SelectObject(self.memory_dc, self.bitmap)
        self.buffer = (ctypes.c_ubyte * (width * height * 4)).from_address(
            self.bits.value)

    def grab(self) -> np.ndarray:
        gdi32.BitBlt(self.memory_dc, 0, 0, self.width, self.height,
                     self.screen_dc, self.x, self.y, SRCCOPY)
        raw = np.frombuffer(self.buffer, dtype=np.uint8).reshape(
            self.height, self.width, 4)
        return raw[:, :, 2::-1]                    # BGRA -> RGB

    def close(self) -> None:
        gdi32.DeleteObject(self.bitmap)
        gdi32.DeleteDC(self.memory_dc)
        user32.ReleaseDC(0, self.screen_dc)


def write_png(path: pathlib.Path, rgb) -> None:
    """Write an RGB array as a PNG, using only the standard library.

    Pillow would be one line, but the interpreter this has to run under has
    numpy and not Pillow, and a probe that will not start is worth nothing. PNG
    needs a signature, IHDR, zlib-compressed scanlines each prefixed with a
    filter byte, and IEND -- little enough to write directly.
    """
    height, width = rgb.shape[0], rgb.shape[1]
    raw = bytearray()
    for row in rgb:
        raw.append(0)                                  # filter type 0, none
        raw += row.tobytes()

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", header)
                     + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
                     + chunk(b"IEND", b""))


def describe(rgb) -> str:
    """Name a colour if it is one Windows itself would have painted."""
    r, g, b = (int(v) for v in rgb)
    known = {
        (240, 240, 240): "COLOR_BTNFACE, the default dialog brush",
        (212, 208, 200): "classic COLOR_BTNFACE",
        (192, 192, 192): "LTGRAY_BRUSH / classic 3D face",
        (128, 128, 128): "GRAY_BRUSH",
        (64, 64, 64): "DKGRAY_BRUSH",
        (255, 255, 255): "WHITE_BRUSH",
    }
    for (kr, kg, kb), name in known.items():
        if abs(r - kr) <= 4 and abs(g - kg) <= 4 and abs(b - kb) <= 4:
            return name
    if max(r, g, b) <= 20:
        return "black"
    if max(r, g, b) - min(r, g, b) <= 8:
        return f"neutral grey {r:02X}, matches no standard brush"
    return "coloured"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--band-y", type=int, default=None)
    parser.add_argument("--band-height", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=10.0,
                        help="mean-channel change that counts as an event")
    parser.add_argument("--capture-above", type=float, default=90.0,
                        help="save a full screenshot when a uniform band is brighter than this")
    parser.add_argument("--captures", type=int, default=6)
    args = parser.parse_args()

    user32.SetProcessDPIAware()
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    y = args.band_y if args.band_y is not None else height // 2

    grabber = BandGrabber(0, y, width, args.band_height)
    full = BandGrabber(0, 0, width, height)
    shots = pathlib.Path(tempfile.mkdtemp(prefix="kmrp-flash-"))
    taken = []
    edge = max(8, width // 40)
    slices = {"left": slice(0, edge),
              "centre": slice(width // 2 - edge, width // 2 + edge),
              "right": slice(width - edge, width)}

    print(f"screen {width}x{height}; band rows {y}..{y + args.band_height}, "
          f"full width")
    print(f"sampling for {args.seconds:.0f}s -- play a movie now\n")

    buckets = 48
    edges_of = np.linspace(0, width, buckets + 1).astype(int)
    times, vectors, profiles = [], [], []
    start = time.perf_counter()
    try:
        while True:
            now = time.perf_counter() - start
            if now >= args.seconds:
                break
            frame = grabber.grab()
            means = np.concatenate([frame[:, s, :].reshape(-1, 3).mean(axis=0)
                                    for s in slices.values()])
            # A coarse profile across the full width, so the horizontal extent of
            # a flash is recoverable without keeping whole frames.
            profile = np.array([frame[:, edges_of[i]:edges_of[i + 1], :].mean()
                                for i in range(buckets)])
            times.append(now)
            vectors.append(means)
            profiles.append(profile)

            # Uniform and bright is the flash. Grab the whole screen once, so
            # its shape -- flat fill, or something with structure in it -- can
            # be looked at rather than inferred.
            if len(taken) < args.captures:
                bright = profile.mean()
                flat = profile.max() - profile.min()
                if bright > args.capture_above and flat < 24:
                    # Grabbing costs about 54 ms and encoding about 146 ms.
                    # Only the grab may happen here; encoding every capture
                    # after the loop keeps the stall short enough that a flash
                    # is still sampled on either side of it.
                    taken.append((now, bright, np.array(full.grab())))
    finally:
        grabber.close()
        full.close()

    elapsed = time.perf_counter() - start
    print(f"{len(times)} samples in {elapsed:.1f}s -- "
          f"{len(times) / elapsed:.0f}/s, {1000 * elapsed / len(times):.2f} ms each\n")

    print(f"{'t (s)':>8} {'held':>7}  {'left':>15} {'centre':>15} {'right':>15}  note")
    previous = None
    changes = []
    for index, (when, vector) in enumerate(zip(times, vectors)):
        if previous is not None and np.abs(vector - previous).max() < args.threshold:
            continue
        previous = vector
        changes.append((index, when, vector))

    for position, (index, when, vector) in enumerate(changes):
        until = changes[position + 1][1] if position + 1 < len(changes) else times[-1]
        cells = " ".join("%15s" % ("(%3d,%3d,%3d)" % tuple(int(v) for v in vector[i:i + 3]))
                         for i in (0, 3, 6))
        note = describe(vector[3:6])
        if note in ("black", "coloured"):
            edges = describe(vector[0:3])
            if edges not in ("black", "coloured"):
                note = f"picture {note}, edges {edges}"
        print(f"{when:8.3f} {until - when:7.3f}  {cells}  {note}")

    # The frames that are uniformly bright-but-colourless are the flash. Show
    # each one's shape across the screen, which is what says whether it is the
    # movie window, the bars beside it, or everything.
    brightness = np.array([v.reshape(3, 3).mean(axis=1).mean() for v in vectors])
    spread = np.array([v.reshape(3, 3).max(axis=1).max() - v.reshape(3, 3).min(axis=1).min()
                       for v in vectors])
    grey = np.where((brightness > 40) & (spread < 30))[0]
    print()
    if not len(grey):
        print("no uniform grey frame was sampled")
        return 0
    print(f"{len(grey)} uniformly grey samples, "
          f"{times[grey[0]]:.3f}s to {times[grey[-1]]:.3f}s")
    ramp = " .:-=+*#%@"
    for index in grey[:: max(1, len(grey) // 12)]:
        shape = "".join(ramp[min(9, int(v) * 10 // 256)] for v in profiles[index])
        print(f"  {times[index]:7.3f}s  mean {brightness[index]:5.1f}  |{shape}|")
    print("  (left edge of the bar is the left edge of the screen; "
          "' ' is black, '@' is white)")
    if taken:
        print(f"\n{len(taken)} full screenshots of the flash:")
        for when, bright, frame in taken:
            path = shots / f"flash_{when:07.3f}s.png"
            write_png(path, np.ascontiguousarray(frame))
            spread = int(frame.max()) - int(frame.min())
            print(f"  {when:7.3f}s  mean {bright:5.1f}  "
                  f"range {frame.min()}..{frame.max()} spread {spread}  {path}")
        print("  spread near zero is a flat fill; larger has structure in it")
    else:
        print("\nno full screenshot triggered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
