#!/bin/zsh
# Builds the KMRP for macOS package: dist/macos/KMRP-macOS-<version>/ and its .zip.
#
#   macos/build.sh --kpm <Kotor-Patch-Manager checkout> --widescreen <K1WidescreenPatch dir>
#                  [--game "<...>/Knights of the Old Republic.app"] [--exe <unmodified KOTOR_Exe>]
#                  [--python <python3>] [--reuse-resources]
#
# Needs: Xcode command line tools (clang, codesign), .NET 8 SDK (KPM's KPatchCore writes
# patch_config.toml), and a Python with requirements.txt installed (the resource build).
# Game files are read, never written: the unmodified KOTOR_Exe (hooks are resolved against
# its hash) and TexturePacks/swpc_tex_gui.erf (source art for the fonts). Nothing from the
# game ends up in the package. See macos/README.md.
set -euo pipefail
setopt extendedglob

HERE=${0:A:h}
ROOT=${HERE:h}
VERSION=$(cat "$HERE/VERSION")
KPM=""
WIDESCREEN=""
GAME="$HOME/Library/Application Support/Steam/steamapps/common/swkotor/Knights of the Old Republic.app"
PYTHON=${KMRP_PYTHON:-python3}
REUSE=0
CLEAN_EXE=""   # an unmodified KOTOR_Exe, when the game's own is patched (e.g. KMRP's backup copy)
while (( $# )); do
    case "$1" in
        --kpm) KPM=${2:A}; shift ;;
        --widescreen) WIDESCREEN=${2:A}; shift ;;
        --game) GAME=${2:A}; shift ;;
        --exe) CLEAN_EXE=${2:A}; shift ;;
        --python) PYTHON=$2; shift ;;
        --reuse-resources) REUSE=1 ;;
        *) print -u2 "unknown option: $1"; exit 2 ;;
    esac
    shift
done
[[ -n "$KPM" && -f "$KPM/src/KotorPatcher/Makefile" ]] || { print -u2 "--kpm must point at a Kotor-Patch-Manager checkout"; exit 2; }
[[ -n "$WIDESCREEN" && -x "$WIDESCREEN/build_mac.sh" ]] || { print -u2 "--widescreen must point at Patches/K1WidescreenPatch (with build_mac.sh)"; exit 2; }

EXE=${CLEAN_EXE:-"$GAME/Contents/MacOS/KOTOR_Exe"}
ERF="$GAME/Contents/Assets/TexturePacks/swpc_tex_gui.erf"
VANILLA_EXE_SHA="c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71"
[[ "$(shasum -a 256 "$EXE" | cut -d' ' -f1)" == "$VANILLA_EXE_SHA" ]] || { print -u2 "$EXE is not the unmodified 1.4.0 build (pass --exe with a clean copy, such as ~/Library/Application Support/KMRP/macos/backup/KOTOR_Exe)"; exit 1; }
[[ -f "$ERF" ]] || { print -u2 "missing $ERF"; exit 1; }

BUILD="$ROOT/build/macos"
NAME="KMRP-macOS-$VERSION"
OUT="$ROOT/dist/macos/$NAME"
PKG="$OUT/kmrp"
step() { print -r -- ""; print -r -- "== $*"; }

rm -rf "$BUILD/engine" "$BUILD/kpatch" "$OUT" "$ROOT/dist/macos/$NAME.zip"
mkdir -p "$BUILD/kpatch" "$PKG/bin" "$PKG/engine" "$PKG/licenses"

# ------------------------------------------------------------------------ engine
step "KotorPatcher.dylib (KotOR Patch Manager's Mac runtime)"
make -C "$KPM/src/KotorPatcher" dylib CXX_MAC=clang++ >/dev/null
cp "$KPM/src/KotorPatcher/build/KotorPatcher.dylib" "$BUILD/"

step "Widescreen patch (with the KMRP engine fixes and UseGuiFileLayouts), the base KMRP runs on"
"$WIDESCREEN/build_mac.sh" "$BUILD/widescreen" >/dev/null
cp "$BUILD/widescreen/K1WidescreenPatch.kpatch" "$BUILD/kpatch/"

step "Map-note corrections patch"
NOTES="$BUILD/map-notes"
rm -rf "$NOTES"; mkdir -p "$NOTES/binaries"
"$PYTHON" "$HERE/tools/make_map_notes_table.py" \
    "$ROOT/third_party/Included/K1-Area-Map-Fixes-1.0.0 by derslok/More info/source/data/note_table.bin" \
    "$NOTES/map_notes_table.inc"
clang++ -arch x86_64 -std=c++17 -O2 -mmacosx-version-min=10.9 -dynamiclib -w -I"$NOTES" \
    -install_name @executable_path/macos_x86_64.dylib \
    -o "$NOTES/binaries/macos_x86_64.dylib" "$HERE/patches/kmrp-map-notes/map_notes.cpp"
codesign --force --sign - "$NOTES/binaries/macos_x86_64.dylib" 2>/dev/null
cp "$HERE/patches/kmrp-map-notes/manifest.toml" "$HERE/patches/kmrp-map-notes/kotor1-steam-aspyr-macos.hooks.toml" "$NOTES/"
(cd "$NOTES" && zip -q -X "$BUILD/kpatch/kmrp-map-notes.kpatch" manifest.toml kotor1-steam-aspyr-macos.hooks.toml binaries/macos_x86_64.dylib)

step "Layout patch (the engine side of KMRP's menu layouts)"
LAYOUT="$BUILD/layout"
rm -rf "$LAYOUT"; mkdir -p "$LAYOUT/binaries"
clang++ -arch x86_64 -std=c++17 -O2 -mmacosx-version-min=10.9 -dynamiclib -w \
    -install_name @executable_path/macos_x86_64.dylib \
    -o "$LAYOUT/binaries/macos_x86_64.dylib" "$HERE/patches/kmrp-layout/"*.cpp
codesign --force --sign - "$LAYOUT/binaries/macos_x86_64.dylib" 2>/dev/null
cp "$HERE/patches/kmrp-layout/manifest.toml" "$HERE/patches/kmrp-layout/kotor1-steam-aspyr-macos.hooks.toml" "$LAYOUT/"
(cd "$LAYOUT" && zip -q -X "$BUILD/kpatch/kmrp-layout.kpatch" manifest.toml kotor1-steam-aspyr-macos.hooks.toml binaries/macos_x86_64.dylib)

step "patch_config.toml, written by KPM's own KPatchCore"
dotnet build "$HERE/tools/kpm-cli" -c Release -p:KpmRoot="$KPM" -o "$BUILD/kpm-cli" >/dev/null
KPMCLI=(dotnet "$BUILD/kpm-cli/kpm-cli.dll")
$KPMCLI validate "$BUILD/kpatch/K1WidescreenPatch.kpatch" "$EXE" | { grep -v DEBUG || true; }
$KPMCLI validate "$BUILD/kpatch/kmrp-map-notes.kpatch" "$EXE" | { grep -v DEBUG || true; }
$KPMCLI validate "$BUILD/kpatch/kmrp-layout.kpatch" "$EXE" | { grep -v DEBUG || true; }
# In this order: the widescreen patch's byte hooks and constructor first, then KMRP's patches,
# whose sites the widescreen patch's switch leaves vanilla (kmrp-layout checks each).
$KPMCLI stage-many "$EXE" "$BUILD/engine/full" "$BUILD/kpatch/K1WidescreenPatch.kpatch" "$BUILD/kpatch/kmrp-map-notes.kpatch" "$BUILD/kpatch/kmrp-layout.kpatch" | { grep -v DEBUG || true; }
$KPMCLI stage-many "$EXE" "$BUILD/engine/no-notes" "$BUILD/kpatch/K1WidescreenPatch.kpatch" "$BUILD/kpatch/kmrp-layout.kpatch" | { grep -v DEBUG || true; }
mkdir -p "$PKG/engine/patches"
cp "$BUILD/KotorPatcher.dylib" "$PKG/engine/"
cp "$BUILD/engine/full/patches/"*.dylib "$PKG/engine/patches/"
cp "$BUILD/engine/full/patch_config.toml" "$PKG/engine/patch_config.toml"
cp "$BUILD/engine/no-notes/patch_config.toml" "$PKG/engine/patch_config.no-map-notes.toml"
cmp -s "$BUILD/engine/full/patches/k1widescreenpatch.dylib" "$BUILD/engine/no-notes/patches/k1widescreenpatch.dylib"
cmp -s "$BUILD/engine/full/patches/kmrp-layout.dylib" "$BUILD/engine/no-notes/patches/kmrp-layout.dylib"

step "kmrp-macho (adds the patcher's load command)"
clang -O2 -Wall -Wextra -arch x86_64 -arch arm64 -mmacosx-version-min=10.13 \
    -o "$PKG/bin/kmrp-macho" "$HERE/tools/kmrp-macho.c"
codesign --force --sign - "$PKG/bin/kmrp-macho" 2>/dev/null

step "kmrp-guiblend and kmrp-abilityicons (the installer's helpers)"
for helper in kmrp-guiblend kmrp-abilityicons; do
    clang -O2 -Wall -Wextra -arch x86_64 -arch arm64 -mmacosx-version-min=10.13 \
        -o "$PKG/bin/$helper" "$HERE/tools/$helper.c"
    codesign --force --sign - "$PKG/bin/$helper" 2>/dev/null
done

# ------------------------------------------------------------------------ content
RESOURCES="$ROOT/build/kmrp/resources"
if (( ! REUSE )) || [[ ! -f "$RESOURCES/override-common.zip" ]]; then
    step "Interface resources (tools/prepare_universal_resources.py, as build_kmrp.ps1 runs it)"
    # The fonts baked at each resolution's own scale, from tools/build_font_scale_sets.py,
    # as build_kmrp.ps1 passes them. Without them every set gets the shared 3.0 bake and the
    # engine resamples the text (issue #16). Until 2026-09-29 this step never passed them;
    # the resources the package had shipped were built by hand with them.
    FONT_SETS=()
    if [[ -d "$ROOT/build/fonts" ]]; then
        FONT_SETS=(--font-scale-sets "$ROOT/build/fonts")
    else
        print -u2 "warning: build/fonts is missing, so every resolution gets the 3.0 font atlas."
        print -u2 "         Run: python tools/build_font_scale_sets.py <erf> build/fonts"
    fi
    "$PYTHON" "$ROOT/tools/prepare_universal_resources.py" \
        "$ROOT/assets/resolution-geometry.json" \
        "$ROOT/third_party/Included/kotor-high-resolution-menus-1.5" \
        "$ROOT/assets/override-3440x1440" "$RESOURCES" "$ERF" "$ROOT/assets/hd-fonts" \
        "${FONT_SETS[@]}" \
        --bundled-override "$ROOT/third_party/Included/Party Portraits by MadDerp" \
                           "$ROOT/third_party/Included/KOTOR1 HD ICON PACK ver1.0 1.0.0 by JackInTheBox/Override" \
        2>&1 | { grep -v "DEBUG" || true; } | tail -3
fi

step "Artwork (override-common.zip, less what macOS does not use)"
# Left out, each for a stated reason (macos/README.md, "What is not installed"):
#   kmr*           KMRP's controller prompt and layout art; the Aspyr port has its own
#                  controller support and KMRP's controller layer is Windows-only
#   the 18 fonts   every resolution's set in layouts.zip carries them at its own size
FONT_NAMES=(dialogfont10x10 dialogfont10x10a dialogfont10x10b dialogfont12x16 dialogfont16x16
            dialogfont16x16a dialogfont16x16b dialogfont32x32 fnt_console fnt_credits fnt_creditsa
            fnt_creditsb fnt_d10x10b fnt_d16x16 fnt_d16x16a fnt_d16x16b fnt_dialog16x16 fnt_galahad14)
mkdir -p "$PKG/override"
unzip -q -o "$RESOURCES/override-common.zip" -d "$PKG/override"
for file in "$PKG/override"/(#i)kmr*(.N); do rm -f "$file"; done
for font in $FONT_NAMES; do rm -f "$PKG/override/$font".(tga|tpc|txi)(N); done
[[ -z "$(find "$PKG/override" -mindepth 1 -type d)" ]] || { print -u2 "override-common.zip has subdirectories"; exit 1; }
cp "$RESOURCES/bundled-override.txt" "$PKG/bundled-override.txt"
print -r -- "$(ls "$PKG/override" | wc -l | tr -d ' ') files"

step "Menu layouts: every resolution's set, pooled, and the blend table for any other"
# The same pool the Windows installer embeds (tools/pack_resolution_layouts.py): each distinct
# file once, and an index per resolution. The installer installs the display's set, or, for a
# size the build has none for, blends the .gui files from gui-blend.bin (tools/
# build_gui_blend_table.py, macos/tools/kmrp-guiblend.c) and takes the fonts and art of the
# nearest set.
"$PYTHON" "$ROOT/tools/pack_resolution_layouts.py" "$RESOURCES" "$PKG/layouts.zip" | tail -2
"$PYTHON" "$ROOT/tools/build_gui_blend_table.py" "$RESOURCES" "$PKG/gui-blend.bin" | tail -1

# ------------------------------------------------------------------------ scripts, docs
step "Installer, documentation, licences"
cp "$HERE/kmrp-mac.sh" "$HERE/VERSION" "$PKG/"
chmod +x "$PKG/kmrp-mac.sh"
cp "$HERE/Install KMRP.command" "$HERE/Uninstall KMRP.command" "$OUT/"
chmod +x "$OUT/"*.command
cp "$HERE/PLAYER-README.md" "$OUT/README.md"
cp "$ROOT/LICENSE" "$PKG/licenses/KMRP-LICENSE.txt"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$PKG/licenses/THIRD_PARTY_NOTICES.md"
cp "$KPM/LICENSE" "$PKG/licenses/KotOR-Patch-Manager-LICENSE.txt" 2>/dev/null || true
cp "$RESOURCES/GPL-3.0-KOTOR-High-Resolution-Menus.txt" "$PKG/licenses/" 2>/dev/null || true

(cd "$PKG" && find . -type f ! -name SHA256SUMS | sed 's|^\./||' | LC_ALL=C sort | while IFS= read -r f; do shasum -a 256 "$f"; done > SHA256SUMS)
print -r -- "$(wc -l < "$PKG/SHA256SUMS" | tr -d ' ') files hashed"

step "Archive"
# Without --norsrc --noextattr, ditto stores each file's extended attributes (every file here
# carries com.apple.provenance) as a ._ AppleDouble entry beside it: until 2026-09-29 the
# archive held 785 of them. Archive Utility folds them back in, but `unzip` writes them out
# as files, and the installer would have copied ._*.tga and ._*.tpc into the game's override.
(cd "$ROOT/dist/macos" && ditto -c -k --norsrc --noextattr --noacl --keepParent "$NAME" "$NAME.zip")
if unzip -Z1 "$ROOT/dist/macos/$NAME.zip" | grep -q '/\._'; then
    print -u2 "the archive holds AppleDouble (._) entries"; exit 1
fi
ls -la "$ROOT/dist/macos/$NAME.zip"
shasum -a 256 "$ROOT/dist/macos/$NAME.zip"
