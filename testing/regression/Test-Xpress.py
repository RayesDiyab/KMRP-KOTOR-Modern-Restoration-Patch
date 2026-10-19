#!/usr/bin/env python3
"""The modules' own XPRESS-Huffman decoder against Windows' encoder.

Since 2026-10-10 the controller patch's module decodes its embedded bank with
src/controller-native/K1Xpress.cpp instead of the Windows Compression API, which Wine
and Proton do not provide (issue 30); KMRP's module did too until 2026-10-19, when its
bank became the art pack, which is LZMA (tools/kmrp_pack.py, checked by
Test-NativeAssetsBank.py). This builds that decoder as an x86 program (Test-Xpress.cmd,
MSVC) and gives it:

  1. every object of the controller patch's built bank,
     build/controller-standalone/controller-assets.bin, each held against the SHA-256
     the bank records for it;
  2. streams made here with the Compression API's Compress(): empty-like and tiny
     inputs, runs, text, random bytes (stored uncompressed), blocks that cross the
     65,536-byte table boundary, long matches, and an input above the container's
     64 MB chunk;
  3. the small streams cut short and with bytes changed, which must not crash it.

Windows only: the encoder is cabinet.dll's. It starts no game.

Documentation standard: see `docs/documentation-standard.md`.
"""
from __future__ import annotations

import hashlib
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import build_native_assets as builder   # noqa: E402

CONTROLLER = ROOT / "build/controller-standalone/controller-assets.bin"
PROGRAM = ROOT / "build/xpress-test/xpress-check.exe"


def controller_objects(blob: bytes):
    """(size, stored bytes, key) of each object of the controller patch's bank (KCAST001)."""
    if blob[:8] != b"KCAST001":
        raise SystemExit(f"{CONTROLLER} is {blob[:8]!r}")
    at = 12
    for _ in range(struct.unpack_from("<I", blob, 8)[0]):
        at += 2 + struct.unpack_from("<H", blob, at)[0]
        size, packed = struct.unpack_from("<II", blob, at + 32)
        yield size, blob[at + 40:at + 40 + packed], blob[at:at + 32]
        at += 40 + packed


def made_here():
    rng = random.Random(30)
    noise = rng.randbytes(4096)
    words = [bytes(rng.choices(b"abcdefghijklmnopqrstuvwxyz ", k=rng.randint(2, 9))) for _ in range(500)]
    text = b"".join(rng.choice(words) for _ in range(600000))
    return {
        "one byte": b"A",
        "seventeen bytes": b"hello hello hello",
        "100 zeros": bytes(100),
        "70,000 zeros (a match longer than 65,535)": bytes(70000),
        "65,535 bytes of text": text[:65535],
        "65,536 bytes of text": text[:65536],
        "65,537 bytes of text": text[:65537],
        "3 MB of text": text[:3000000],
        "1,000 random bytes": rng.randbytes(1000),
        "200,000 random bytes": rng.randbytes(200000),
        "random then zeros": rng.randbytes(1100000) + bytes(1200000),
        "a 4,096-byte pattern repeated": noise * 300,
        "text with long runs": b"".join(text[i:i + 5000] + bytes([i & 255]) * (i % 90000) for i in range(0, 400000, 5000)),
        "70 MB, above one chunk": (noise + text[:60000]) * 1093,
    }


def main() -> int:
    for needed in (CONTROLLER,):
        if not needed.exists():
            raise SystemExit(f"{needed} is missing: build the modules first")
    subprocess.run(["cmd.exe", "/c", str(ROOT / "testing/regression/Test-Xpress.cmd")], check=True)
    failed = False
    with tempfile.TemporaryDirectory() as tmp:
        compressor = builder.Compressor()
        sets = {
            "the controller patch's bank": controller_objects(CONTROLLER.read_bytes()),
            "streams made here": ((len(data), compressor.compress(data), hashlib.sha256(data).digest())
                                  for data in made_here().values()),
        }
        for name, vectors in sets.items():
            path = Path(tmp) / "vectors.bin"
            with path.open("wb") as out:
                for size, packed, key in vectors:
                    out.write(struct.pack("<II", size, len(packed)) + key + packed)
            done = subprocess.run([str(PROGRAM), str(path)], capture_output=True, text=True)
            ok = done.returncode == 0
            failed |= not ok
            print(("ok    " if ok else "FAIL  ") + f"{name}: {done.stdout.strip() or done.returncode}")
        compressor.close()
    print()
    print("a check failed" if failed else "all checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
