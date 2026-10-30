#!/bin/bash
# KMRP's Linux installer as an AppImage (issue 76, docs/linux-appimage-installer.md).
#
# Run on Linux (on the build PC: WSL's Ubuntu, from tools/build_linux_installer.ps1) after
# the program is published to build/installer-linux/publish. Packs it with appimagetool
# 1.9.1 from the AppImage project's GitHub release, downloaded once into build/tools and
# checked against the SHA-256 GitHub publishes for it.
#
#   tools/build_linux_appimage.sh VERSION
set -euo pipefail
VERSION="${1:?usage: build_linux_appimage.sh VERSION}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/build/installer-linux"
PUBLISH="$OUT/publish"
TOOL="$ROOT/build/tools/appimagetool-x86_64.AppImage"
TOOL_URL="https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage"
TOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"

if [ ! -f "$TOOL" ] || ! echo "$TOOL_SHA256  $TOOL" | sha256sum -c --status -; then
    mkdir -p "$(dirname "$TOOL")"
    curl -fsSL -o "$TOOL" "$TOOL_URL"
    echo "$TOOL_SHA256  $TOOL" | sha256sum -c -
fi
chmod +x "$TOOL"

# The AppDir: the program and the two native libraries the window draws with, the launcher,
# the desktop entry and the icon (the Windows installer's, made into a PNG by the caller).
APPDIR="$OUT/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
cp "$PUBLISH/kmrp-installer" "$PUBLISH/libSkiaSharp.so" "$PUBLISH/libHarfBuzzSharp.so" "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/kmrp-installer"
cp "$OUT/kmrp-installer.png" "$APPDIR/kmrp-installer.png"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/kmrp-installer" "$@"
EOF
chmod +x "$APPDIR/AppRun"
cat > "$APPDIR/kmrp-installer.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=KMRP Installer
Comment=KOTOR Modern Restoration Patch for Star Wars: Knights of the Old Republic on Steam with Proton
Exec=kmrp-installer
Icon=kmrp-installer
Categories=Game;
Terminal=false
EOF

TARGET="$ROOT/dist/KMRP-Linux-$VERSION-x86_64.AppImage"
mkdir -p "$ROOT/dist"
rm -f "$TARGET"
# No FUSE in WSL: the tool runs from its own extraction.
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" --no-appstream "$APPDIR" "$TARGET"
ls -la "$TARGET"
sha256sum "$TARGET"
