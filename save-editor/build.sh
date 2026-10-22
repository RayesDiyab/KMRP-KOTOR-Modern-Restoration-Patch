#!/bin/sh
# Builds the KMRP Save Editor for Linux or macOS into dist/ beside this file:
#   Linux:  dist/kmrp-save-editor
#   macOS:  dist/KMRP Save Editor.app
#
#   sh save-editor/build.sh
#
# Needs Rust (rustup, stable); everything else is in this folder, so it builds on its own,
# outside KMRP (build.rs says where KMRP's fonts are looked for). On Linux the window also
# needs the usual X11/Wayland and fontconfig development packages.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
cargo test --release
cargo build --release
mkdir -p "$here/dist"
bin="$here/build/target/release/kmrp-save-editor"
if [ "$(uname)" = "Darwin" ]; then
    app="$here/dist/KMRP Save Editor.app"
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
    cp "$bin" "$here/dist/kmrp-save-editor"
    echo "$here/dist/kmrp-save-editor"
fi
