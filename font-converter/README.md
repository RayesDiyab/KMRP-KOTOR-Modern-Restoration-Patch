# KMRP Font Converter

Turns any font file into Star Wars: Knights of the Old Republic's font atlases, sized the
way KMRP's (New) Original HD Font is. One Windows program, .NET Framework 4, no other
files; it also runs under Wine and Proton.

How it works and what it writes: [docs/font-converter.md](docs/font-converter.md).

## Building

This folder builds on its own; nothing outside it is needed.
`powershell -ExecutionPolicy Bypass -File build.ps1` makes
`dist\KMRP Font Converter.exe` with the .NET Framework 4 C# compiler that ships with
Windows.

The examples on its tiles and the font metrics it keeps are in `data/`, made by
`make_data.py` from KMRP's `assets/hd-original-fonts`. After that font changes, run
`build.ps1 -Refresh` from a KMRP checkout (needs Python with Pillow) to make them again.

GPL-3.0-or-later, like KMRP. Created by RaymanGT.
