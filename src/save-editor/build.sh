#!/bin/sh
# Builds the KMRP Save Editor for Linux or macOS into dist/:
#   Linux:  dist/kmrp-save-editor
#   macOS:  dist/KMRP Save Editor.app
#
#   sh src/save-editor/build.sh
#
# Needs Rust (rustup, stable) and, the first time, Python 3 with numpy, potrace, fontTools
# and Pillow to make KMRP's fonts (tools/build_hd_original_otf.py). On Linux the window
# also needs the usual X11/Wayland and fontconfig development packages.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
cd "$here"
cargo test --release
cargo build --release
mkdir -p "$root/dist"
bin="$root/build/save-editor-target/release/kmrp-save-editor"
if [ "$(uname)" = "Darwin" ]; then
    app="$root/dist/KMRP Save Editor.app"
    rm -rf "$app"
    mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
    cp "$bin" "$app/Contents/MacOS/kmrp-save-editor"
    cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>KMRP Save Editor</string>
<key>CFBundleDisplayName</key><string>KMRP Save Editor</string>
<key>CFBundleIdentifier</key><string>com.raymangt.kmrp-save-editor</string>
<key>CFBundleExecutable</key><string>kmrp-save-editor</string>
<key>CFBundleShortVersionString</key><string>1.0</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
    echo "$app"
else
    cp "$bin" "$root/dist/kmrp-save-editor"
    echo "$root/dist/kmrp-save-editor"
fi
