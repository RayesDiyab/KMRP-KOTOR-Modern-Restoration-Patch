# LZMA SDK 26.04, the decoder

The five files the SDK names for its ANSI-C LZMA decoder (`DOC/lzma.txt`, "To use
ANSI-C LZMA Decoder you need the following files"), copied unchanged from the official
LZMA SDK 26.04 by Igor Pavlov, as linked from <https://www.7-zip.org/sdk.html>:

| Archive | Bytes | SHA-256 |
| --- | --- | --- |
| `lzma2604.7z` | 1,786,965 | `bd98058d0e12c5da970dd4e5e1d8fa24f2d704914d96e69c28f92ed45421a439` |

| File | SHA-256 |
| --- | --- |
| `LzmaDec.c` | `8a9d33dd01259a71b3c3cfbf645d06944bef65a152d307671372c332e9e0e022` |
| `LzmaDec.h` | `3a3b0ece1ba58601a8265a421a91b9720b39ee92ce898fadecb22f052bc3011f` |
| `7zTypes.h` | `126c3ce886391042443fcc82764d26be7aacda2298588c6ec9bb7ce8c7b47732` |
| `Precomp.h` | `88acadbc12902012872fa29337c86564bb8f9198d6be416aad6119bb537425d1` |
| `Compiler.h` | `cfafaa89ba98a7f4f38cc589533fc03facb98ae1176dfe29d58217767ed5f149` |

They keep the SDK's CRLF line endings (`.gitattributes` marks them `-text`), so the
hashes hold on every checkout. Do not edit them: a change belongs in KMRP's own code
around them (`src/controller-native/K1AssetPack.cpp`).

KMRP's module decodes its art pack, `kmrp-assets.pack`, with them. The pack is written
by `tools/kmrp_pack.py` with Python's own LZMA encoder (liblzma), whose raw LZMA1
streams this decoder reads.

## Licence

Public domain. From the SDK's `DOC/lzma-sdk.txt`: "LZMA SDK is written and placed in
the public domain by Igor Pavlov." Anyone may copy, change, use and distribute it, in
source or compiled form, for any purpose. See also `THIRD_PARTY_NOTICES.md`.
