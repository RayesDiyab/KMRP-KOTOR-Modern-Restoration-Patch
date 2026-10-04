#!/bin/zsh
# Builds the KMRP for macOS package: dist/macos/KMRP-macOS-<version>/ (KMRP Installer.app, which
# carries the installer and everything it installs, and README.md), its .dmg (the Mac download)
# and its .zip (for sites that take only archives).
#
#   macos/build.sh [--game "<...>/Knights of the Old Republic.app"] [--exe <unmodified KOTOR_Exe>]
#                  [--python <python3>] [--reuse-resources]
#                  [--kpm <Kotor-Patch-Manager checkout>] [--widescreen <K1WidescreenPatch dir>]
#
# KPM, the widescreen patch and the Stray Bug Fixes patch come from the submodule
# third_party/Kotor-Patch-Manager (git submodule update --init): the kmrp branch of
# RayesDiyab/Kotor-Patch-Manager, FTD's widescreen-patch branch as KMRP takes it. --kpm and
# --widescreen build from other checkouts instead.
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
KPM="$ROOT/third_party/Kotor-Patch-Manager"
WIDESCREEN=""   # default: $KPM/Patches/K1WidescreenPatch
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
WIDESCREEN=${WIDESCREEN:-"$KPM/Patches/K1WidescreenPatch"}
[[ "$PYTHON" == */* ]] && PYTHON=${PYTHON:a}   # a path, made absolute (not resolved: a venv's python is a link) for steps run elsewhere
[[ -f "$KPM/src/KotorPatcher/Makefile" ]] || { print -u2 "no KotOR Patch Manager at $KPM: run git submodule update --init, or pass --kpm"; exit 2; }
[[ -f "$WIDESCREEN/manifest.toml" ]] || { print -u2 "--widescreen must point at Patches/K1WidescreenPatch"; exit 2; }
[[ -f "$KPM/Patches/create-patch.py" ]] || { print -u2 "no Patches/create-patch.py in $KPM"; exit 2; }

EXE=${CLEAN_EXE:-"$GAME/Contents/MacOS/KOTOR_Exe"}
ERF="$GAME/Contents/Assets/TexturePacks/swpc_tex_gui.erf"
VANILLA_EXE_SHA="c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71"
[[ "$(shasum -a 256 "$EXE" | cut -d' ' -f1)" == "$VANILLA_EXE_SHA" ]] || { print -u2 "$EXE is not the unmodified 1.4.0 build (pass --exe with a clean copy, such as ~/Library/Application Support/KMRP/macos/backup/KOTOR_Exe)"; exit 1; }
[[ -f "$ERF" ]] || { print -u2 "missing $ERF"; exit 1; }

BUILD="$ROOT/build/macos"
NAME="KMRP-macOS-$VERSION"
OUT="$ROOT/dist/macos/$NAME"
INSTALLER="$OUT/KMRP Installer.app"
PKG="$INSTALLER/Contents/Resources/kmrp"   # kmrp-mac.sh and its payload, inside the app
step() { print -r -- ""; print -r -- "== $*"; }

rm -rf "$BUILD/engine" "$BUILD/kpatch" "$OUT" "$ROOT/dist/macos/$NAME.zip" "$ROOT/dist/macos/$NAME.dmg"
mkdir -p "$BUILD/kpatch" "$PKG/bin" "$PKG/engine" "$PKG/licenses"

# ------------------------------------------------------------------------ engine
step "KotorPatcher.dylib (KotOR Patch Manager's Mac runtime)"
make -C "$KPM/src/KotorPatcher" dylib CXX_MAC=clang++ >/dev/null
cp "$KPM/src/KotorPatcher/build/KotorPatcher.dylib" "$BUILD/"

step "Map-note table (Derslok's corrections, compiled into the kmrp patch)"
NOTES="$BUILD/map-notes"
rm -rf "$NOTES"; mkdir -p "$NOTES"
"$PYTHON" "$HERE/tools/make_map_notes_table.py" \
    "$ROOT/third_party/Included/K1-Area-Map-Fixes-1.0.0 by derslok/More info/source/data/note_table.bin" \
    "$NOTES/map_notes_table.inc"

step "SDL 3.4.16 for the controller (the official release Windows pins too, tools/prepare_sdl3.ps1)"
SDL_DMG="$ROOT/build/deps/SDL3-3.4.16.dmg"
SDL_SHA=675660a9e457239af615f9e41f788612168d1639b9d2eda2957e8dace26687fd
SDL_DIR="$ROOT/build/deps/SDL3-3.4.16-macos"
if [[ ! -f "$SDL_DIR/SDL3.framework/Versions/A/SDL3" ]]; then
    mkdir -p "$ROOT/build/deps"
    [[ -f "$SDL_DMG" ]] || curl -sSL -o "$SDL_DMG" \
        https://github.com/libsdl-org/SDL/releases/download/release-3.4.16/SDL3-3.4.16.dmg
    [[ "$(shasum -a 256 "$SDL_DMG" | cut -d' ' -f1)" == "$SDL_SHA" ]] || { print -u2 "SDL3 image hash mismatch; refusing this dependency"; exit 1; }
    SDL_MOUNT=$(mktemp -d)
    hdiutil attach -nobrowse -readonly -mountpoint "$SDL_MOUNT" "$SDL_DMG" >/dev/null
    rm -rf "$SDL_DIR"; mkdir -p "$SDL_DIR"
    ditto "$SDL_MOUNT/SDL3.xcframework/macos-arm64_x86_64/SDL3.framework" "$SDL_DIR/SDL3.framework"
    cp "$SDL_MOUNT/LICENSE.txt" "$SDL_DIR/LICENSE.txt"
    hdiutil detach "$SDL_MOUNT" >/dev/null
fi
lipo "$SDL_DIR/SDL3.framework/Versions/A/SDL3" -verify_arch x86_64

step "kmrp-macho (adds the patcher's load command)"
clang -O2 -Wall -Wextra -arch x86_64 -arch arm64 -mmacosx-version-min=10.13 \
    -o "$PKG/bin/kmrp-macho" "$HERE/tools/kmrp-macho.c"
codesign --force --sign - "$PKG/bin/kmrp-macho" 2>/dev/null

step "kmrp-guiblend (the installer app checks a custom size with its dry run)"
# kmrp-abilityicons and kmrp-gameart were packaged too until 2026-10-04, when the installer made
# the game-derived art; the module makes it now, with all three compiled in (make_kmrp_patch.py).
clang -O2 -Wall -Wextra -arch x86_64 -arch arm64 -mmacosx-version-min=10.13 \
    -o "$PKG/bin/kmrp-guiblend" "$HERE/tools/kmrp-guiblend.c"
codesign --force --sign - "$PKG/bin/kmrp-guiblend" 2>/dev/null

# ------------------------------------------------------------------------ content
# What the module carries (since 2026-10-04; the installer put it in the game's override folder
# before): laid out here as the package used to hold it, then packed into one bank.
RESOURCES="$ROOT/build/kmrp/resources"
ASRC="$BUILD/assets-src"
rm -rf "$ASRC"; mkdir -p "$ASRC/engine"
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
# Left out, for a stated reason (macos/README.md, "What is not installed"):
#   the 18 fonts   every resolution's set in layouts.zip carries them at its own size
# KMRP's controller art (kmr*) is kept: the controller patch paints its button prompts with it.
FONT_NAMES=(dialogfont10x10 dialogfont10x10a dialogfont10x10b dialogfont12x16 dialogfont16x16
            dialogfont16x16a dialogfont16x16b dialogfont32x32 fnt_console fnt_credits fnt_creditsa
            fnt_creditsb fnt_d10x10b fnt_d16x16 fnt_d16x16a fnt_d16x16b fnt_dialog16x16 fnt_galahad14)
mkdir -p "$ASRC/override"
unzip -q -o "$RESOURCES/override-common.zip" -d "$ASRC/override"
for font in $FONT_NAMES; do rm -f "$ASRC/override/$font".(tga|tpc|txi)(N); done
[[ -z "$(find "$ASRC/override" -mindepth 1 -type d)" ]] || { print -u2 "override-common.zip has subdirectories"; exit 1; }
cp "$RESOURCES/bundled-override.txt" "$ASRC/bundled-override.txt"
print -r -- "$(ls "$ASRC/override" | wc -l | tr -d ' ') files"

step "Menu layouts: every resolution's set, pooled, and the blend table for any other"
# The same pool the Windows installer embeds (tools/pack_resolution_layouts.py): each distinct
# file once, and an index per resolution. The installer installs the display's set, or, for a
# size the build has none for, blends the .gui files from gui-blend.bin (tools/
# build_gui_blend_table.py, macos/tools/kmrp-guiblend.c) and takes the fonts and art of the
# nearest set.
"$PYTHON" "$ROOT/tools/pack_resolution_layouts.py" "$RESOURCES" "$ASRC/layouts.zip" | tail -2
"$PYTHON" "$ROOT/tools/build_gui_blend_table.py" "$RESOURCES" "$ASRC/gui-blend.bin" | tail -1
# The installer keeps the table, for its custom-size check, and the list of sizes with a set of
# their own (it read both from layouts.zip until 2026-10-04).
cp "$ASRC/gui-blend.bin" "$PKG/gui-blend.bin"
unzip -Z1 "$ASRC/layouts.zip" 'index/*' | sed -n 's|^index/\([0-9]*x[0-9]*\)\.txt$|\1|p' > "$PKG/sizes.txt"
[[ -s "$PKG/sizes.txt" ]] || { print -u2 "layouts.zip lists no set"; exit 1; }

step "List rows: the committed offsets are what these sets and this artwork measure to"
# macos/patches/kmrp-assets/list_rows.inc is compiled into the module (layout.cpp, "List rows").
"$PYTHON" "$HERE/tools/measure_list_rows.py" "$ASRC/layouts.zip" "$ASRC/override" --check 2>/dev/null || {
    print -u2 "run: $PYTHON macos/tools/measure_list_rows.py $ASRC/layouts.zip $ASRC/override"; exit 1; }

step "The bank: artwork, every menu set, the blend table and SDL, for the module"
# SDL itself, under the name the module unpacks it as. Its code is unchanged; its signature is
# redone because the release's (ad-hoc, like ours) seals the framework's Info.plist, which
# does not travel with the bare library.
cp "$SDL_DIR/SDL3.framework/Versions/A/SDL3" "$ASRC/engine/kmrp-sdl3.dylib"
codesign --force --sign - --identifier org.libsdl.SDL3 "$ASRC/engine/kmrp-sdl3.dylib" 2>/dev/null
codesign --verify "$ASRC/engine/kmrp-sdl3.dylib"
BANK="$BUILD/assets/kmrp-assets.bin"
"$PYTHON" "$HERE/tools/make_kmrp_assets.py" --package "$ASRC" --out "$BANK"

step "The patches: FTD's Widescreen Patch and Stray Bug Fixes, and KMRP's own on top of them"
# Three KotOR Patch Manager patches since 2026-10-04 (one until then, id kmrp, which carried a
# copy of FTD's two since 2026-09-30):
#
#   K1StrayBugFixes.kpatch    FTD's, built from the submodule's source with KPM's own
#   K1WidescreenPatch.kpatch  Patches/create-patch.py, as every KPM patch is built
#   kmrp.kpatch               KMRP's own code (tools/make_kmrp_patch.py --split): the menu sets
#                             and artwork (the bank above), the resolution chosen in the game,
#                             KMRP's navigation and status summary, map notes, the controller.
#                             It requires the two, and asks the Widescreen Patch for its .gui
#                             mode through that patch's entry points.
#
# Controller support, map notes and debug logs are kmrp's patch options
# (LaneDibello/Kotor-Patch-Manager#310), recorded in configs/kmrp.ini, which the module reads.
# Only the controller's hooks depend on an option, so the installer needs two hook lists: the
# whole install, and the install without them. Each is staged by KPM's own KPatchCore; the second
# from the list make_kmrp_patch.py writes for an installer that resolved the option
# (--without-option), since the submodule's KPatchCore is from before patch options.
STRAY="$KPM/Patches/K1StrayBugFixes"
[[ -f "$STRAY/manifest.toml" ]] || { print -u2 "no Patches/K1StrayBugFixes in $KPM"; exit 2; }
grep -q K1Widescreen_UseGuiFileLayouts "$WIDESCREEN/mac_widescreen.cpp" || {
    print -u2 "the Widescreen Patch in $WIDESCREEN has no entry points for KMRP (K1Widescreen_UseGuiFileLayouts): KMRP needs FTD's patch with its 2026-10-04 adjustment. Pass --kpm with a KotOR Patch Manager tree that has it."
    exit 2
}
dotnet build "$HERE/tools/kpm-cli" -c Release -p:KpmRoot="$KPM" -o "$BUILD/kpm-cli" >/dev/null
KPMCLI=(dotnet "$BUILD/kpm-cli/kpm-cli.dll")
mkdir -p "$PKG/engine" "$BUILD/kpatch/ftd"
for patch in K1StrayBugFixes K1WidescreenPatch; do
    (cd "$KPM/Patches/$patch" && "$PYTHON" ../create-patch.py -o "$BUILD/kpatch/ftd" >"$BUILD/kpatch/ftd/$patch.log" 2>&1) ||
        { cat "$BUILD/kpatch/ftd/$patch.log" >&2; print -u2 "$patch does not build"; exit 1; }
    [[ -f "$BUILD/kpatch/ftd/$patch.kpatch" ]] || { print -u2 "create-patch.py made no $patch.kpatch"; exit 1; }
    $KPMCLI validate "$BUILD/kpatch/ftd/$patch.kpatch" "$EXE" | { grep -v DEBUG || true; }
done
kmrp_patch() {   # kmrp_patch <folder> [make_kmrp_patch.py options]: built, checked and staged with FTD's two
    local name=$1; shift
    mkdir -p "$BUILD/kpatch/$name"
    "$PYTHON" "$HERE/tools/make_kmrp_patch.py" --split --widescreen "$WIDESCREEN" --stray "$STRAY" \
        --layout "$HERE/patches/kmrp-layout" --notes "$HERE/patches/kmrp-map-notes" --notes-include "$NOTES" \
        --controller "$HERE/patches/kmrp-controller" --sdl "$SDL_DIR" --version "$VERSION" --options "$@" \
        --assets "$HERE/patches/kmrp-assets" --assets-bank "$BANK" --tools "$HERE/tools" \
        --out "$BUILD/kpatch/$name/kmrp.kpatch"
    $KPMCLI validate "$BUILD/kpatch/$name/kmrp.kpatch" "$EXE" | { grep -v DEBUG || true; }
    # In KPM's order: a patch after the ones it requires. Its overlap check runs across all three.
    $KPMCLI stage-many "$EXE" "$BUILD/engine/$name" "$BUILD/kpatch/ftd/K1StrayBugFixes.kpatch" \
        "$BUILD/kpatch/ftd/K1WidescreenPatch.kpatch" "$BUILD/kpatch/$name/kmrp.kpatch" | { grep -v DEBUG || true; }
    grep -q '^id = "kmrp"$' "$BUILD/engine/$name/patch_config.toml" || { print -u2 "$name: not staged"; exit 1; }
}
kmrp_patch kmrp
kmrp_patch kmrp.controller-off --without-option controller
# The same modules whatever was chosen: the choice is in the hook list and in configs/kmrp.ini.
for module in kmrp k1widescreenpatch k1-stray-bug-fixes-patch; do
    cmp -s "$BUILD/engine/kmrp/patches/$module.dylib" "$BUILD/engine/kmrp.controller-off/patches/$module.dylib" \
        || { print -u2 "the two stagings hold different $module modules"; exit 1; }
done
# The option's hooks are exactly what the second list lacks, and it carries no condition.
"$PYTHON" - "$BUILD/kpatch/kmrp/kmrp.kpatch" "$BUILD/engine/kmrp/patch_config.toml" \
    "$BUILD/engine/kmrp.controller-off/patch_config.toml" <<'PY'
import sys, tomllib, zipfile
patch, on, off = sys.argv[1:]
with zipfile.ZipFile(patch) as z:
    name = next(n for n in z.namelist() if n.endswith(".hooks.toml"))
    declared = tomllib.loads(z.read(name).decode())["hooks"]
    manifest = tomllib.loads(z.read("manifest.toml").decode())["patch"]
    options = [o["id"] for o in manifest["options"]]
def staged(path):
    patches = tomllib.loads(open(path, "rb").read().decode())["patches"]
    return [p["id"] for p in patches], {p["id"]: [h["address"] for h in p.get("hooks", [])] for p in patches}
ids_on, hooks_on = staged(on)
ids_off, hooks_off = staged(off)
order = ["k1-stray-bug-fixes-patch", "k1widescreenpatch", "kmrp"]
if ids_on != order or ids_off != order or manifest["requires"] != order[:2]:
    sys.exit(f"the staged patches are {ids_on} and {ids_off}, kmrp requires {manifest['requires']}")
conditions = {h.get("when") for h in declared} - {None}
if options != ["controller", "map-notes", "debug-logs"] or conditions != {"controller"}:
    sys.exit(f"kmrp.kpatch: options {options}, conditions {sorted(conditions)}")
everything = [a for i in order for a in hooks_on[i]]
if len(set(everything)) != len(everything):
    sys.exit("two of the three patches hook one address, which KotOR Patch Manager refuses")
if hooks_on["kmrp"] != [h["address"] for h in declared]:
    sys.exit("the staged hook list is not the patch's")
if hooks_off["kmrp"] != [h["address"] for h in declared if "when" not in h]:
    sys.exit("the list without the controller is not the patch's unconditional hooks")
if any(hooks_on[i] != hooks_off[i] for i in order[:2]):
    sys.exit("the two stagings differ in FTD's patches")
print(f"kmrp.kpatch: {len(declared)} hooks, {len(hooks_off['kmrp'])} without the controller; options {', '.join(options)}; "
      f"with FTD's {len(hooks_on[order[0]])} and {len(hooks_on[order[1]])}")
PY
# The modules are not packaged a second time: KMRP's is 150 MB with the menu sets inside, and the
# installer takes each out of its .kpatch, as KPM does (binaries/macos_x86_64.dylib).
for pair in kmrp:kmrp/kmrp.kpatch k1widescreenpatch:ftd/K1WidescreenPatch.kpatch k1-stray-bug-fixes-patch:ftd/K1StrayBugFixes.kpatch; do
    cmp -s "$BUILD/engine/kmrp/patches/${pair%%:*}.dylib" <(unzip -p "$BUILD/kpatch/${pair#*:}" binaries/macos_x86_64.dylib) \
        || { print -u2 "the staged ${pair%%:*} module is not the one in its .kpatch"; exit 1; }
done
cp "$BUILD/engine/kmrp/patch_config.toml" "$PKG/engine/"
cp "$BUILD/engine/kmrp.controller-off/patch_config.toml" "$PKG/engine/patch_config.controller-off.toml"
# The patches themselves, which the installer takes the modules from and puts in KotOR Patch
# Manager's patch folder, as the Windows installer does with its .kpatch files, so KPM lists them.
cp "$BUILD/kpatch/kmrp/kmrp.kpatch" "$BUILD/kpatch/ftd/K1WidescreenPatch.kpatch" "$BUILD/kpatch/ftd/K1StrayBugFixes.kpatch" "$PKG/engine/"
cp "$BUILD/KotorPatcher.dylib" "$PKG/engine/"
cp "$SDL_DIR/LICENSE.txt" "$PKG/licenses/SDL3-LICENSE.txt"


# ------------------------------------------------------------------------ scripts, docs
step "Installer, documentation, licences"
cp "$HERE/kmrp-mac.sh" "$HERE/VERSION" "$PKG/"
chmod +x "$PKG/kmrp-mac.sh"
cp "$HERE/PLAYER-README.md" "$OUT/README.md"
cp "$ROOT/LICENSE" "$PKG/licenses/KMRP-LICENSE.txt"
cp "$ROOT/THIRD_PARTY_NOTICES.md" "$PKG/licenses/THIRD_PARTY_NOTICES.md"
cp "$KPM/LICENSE" "$PKG/licenses/KotOR-Patch-Manager-LICENSE.txt" 2>/dev/null || true
cp "$RESOURCES/GPL-3.0-KOTOR-High-Resolution-Menus.txt" "$PKG/licenses/" 2>/dev/null || true

(cd "$PKG" && find . -type f ! -name SHA256SUMS | sed 's|^\./||' | LC_ALL=C sort | while IFS= read -r f; do shasum -a 256 "$f"; done > SHA256SUMS)
print -r -- "$(wc -l < "$PKG/SHA256SUMS" | tr -d ' ') files hashed"

step "KMRP Installer.app (the window over kmrp-mac.sh, macos/installer-app)"
# Every size the app lists must be one the package has a set for.
missing=()
for size in $(awk -F '\t' '$1 ~ /^[0-9]+x[0-9]+$/ { print $1 }' "$HERE/installer-app/resolutions.txt"); do
    grep -qx "$size" "$PKG/sizes.txt" || missing+=($size)
done
(( ${#missing} == 0 )) || { print -u2 "resolutions.txt lists sizes the build has no set for: $missing"; exit 1; }
mkdir -p "$INSTALLER/Contents/MacOS"
clang -fobjc-arc -O2 -Wall -Wextra -Wno-unused-parameter -arch x86_64 -arch arm64 -mmacosx-version-min=10.13 \
    -Wunguarded-availability -framework Cocoa -framework Accelerate -weak_framework UniformTypeIdentifiers \
    -o "$INSTALLER/Contents/MacOS/KMRP Installer" "$HERE/installer-app/main.m"
sed "s/@VERSION@/$VERSION/g" "$HERE/installer-app/Info.plist" > "$INSTALLER/Contents/Info.plist"
plutil -lint "$INSTALLER/Contents/Info.plist" >/dev/null
cp "$HERE/installer-app/resolutions.txt" "$INSTALLER/Contents/Resources/"
# The Windows patcher's own art: its brand lockup and its step and state icons
# (build_kmrp.ps1 embeds the same files), so the two windows look alike.
cp "$ROOT/src/patcher/brand.png" "$INSTALLER/Contents/Resources/"
for icon in folder shield monitor tools verified missing Settings; do
    cp "$ROOT/src/patcher/icons/$icon.png" "$INSTALLER/Contents/Resources/"
done
# KMRP's icon on the Mac, the disk image's art with it (tools/make_package_art.py): the crest
# over "KMRP", for the app and, below, for the disk.
ART="$BUILD/art"
rm -rf "$ART"
"$PYTHON" "$HERE/tools/make_package_art.py" "$ART" "$VERSION" >/dev/null
cp "$ART/Icon.icns" "$INSTALLER/Contents/Resources/AppIcon.icns"
# Ad hoc, as every binary here: the signature seals the bundle, so a changed file shows as
# damaged. Without a Developer ID and notarization, Gatekeeper asks the player to allow the
# app once (PLAYER-README.md, Install).
codesign --force --sign - "$INSTALLER"
codesign --verify --strict "$INSTALLER"

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

step "Disk image"
# What a Mac player downloads: KMRP Installer and a link to /Applications, in a window that
# says to drag one onto the other (macos/tools/make_package_art.py: the installer's art
# direction, its own composition). The README stays in the zip; the window carries the one step
# a first launch needs. HFS+ with LZFSE compression (ULFO), both readable from macOS 10.11,
# below the app's 10.13. It keeps the bundle exactly as built and signed, and the installer
# never writes into its own bundle, so it also runs straight from the mounted image.
#
# The window's look lives in the volume's .DS_Store, which Finder writes: the image is made
# writable, mounted where Finder sees it, laid out by AppleScript, then compressed. Finder
# needs the build's terminal to be allowed to control it (System Settings, Privacy & Security,
# Automation); without that the image is made plain, with a warning, rather than not at all.
DMG="$ROOT/dist/macos/$NAME.dmg"
VOLUME="KMRP $VERSION"
DMGWORK="$BUILD/dmg"
rm -rf "$DMGWORK"; mkdir -p "$DMGWORK"
tiffutil -cathidpicheck "$ART/background.png" "$ART/background@2x.png" -out "$DMGWORK/background.tiff" 2>/dev/null
[[ -d "/Volumes/$VOLUME" ]] && { print -u2 "a volume named $VOLUME is already mounted; eject it first"; exit 1; }
SIZE_MB=$(( $(du -sm "$INSTALLER" | cut -f1) + 40 ))
hdiutil create -quiet -size "${SIZE_MB}m" -fs HFS+ -volname "$VOLUME" -ov "$DMGWORK/rw.dmg"
hdiutil attach -quiet -noautoopen -noverify "$DMGWORK/rw.dmg"
ditto "$INSTALLER" "/Volumes/$VOLUME/KMRP Installer.app"
ln -s /Applications "/Volumes/$VOLUME/Applications"
mkdir "/Volumes/$VOLUME/.background"
cp "$DMGWORK/background.tiff" "/Volumes/$VOLUME/.background/background.tiff"
cp "$ART/Icon.icns" "/Volumes/$VOLUME/.VolumeIcon.icns"
SetFile -a C "/Volumes/$VOLUME" 2>/dev/null || true   # the disk shows the crest
styled=1
if ! osascript >/dev/null 2>"$DMGWORK/finder.log" <<APPLESCRIPT
tell application "Finder"
    tell disk "$VOLUME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {160, 120, 800, 580}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 104
        set text size of viewOptions to 13
        set background picture of viewOptions to file ".background:background.tiff"
        set position of item "KMRP Installer.app" of container window to {170, 262}
        set position of item "Applications" of container window to {470, 262}
        close
        open
        delay 1
        close
    end tell
end tell
APPLESCRIPT
then
    styled=0
    print -u2 "warning: Finder could not lay out the disk image's window ($(tr '\n' ' ' < "$DMGWORK/finder.log")); it is plain"
fi
sync
rm -rf "/Volumes/$VOLUME/.fseventsd" "/Volumes/$VOLUME/.Trashes" 2>/dev/null || true
hdiutil detach -quiet "/Volumes/$VOLUME" || hdiutil detach -quiet -force "/Volumes/$VOLUME"
hdiutil convert -quiet "$DMGWORK/rw.dmg" -format ULFO -ov -o "$DMG"
rm -f "$DMGWORK/rw.dmg"

# Checked as a player gets it: mounted read-only, the app and the Applications link at its root
# (hidden files aside), the app's signature intact, the payload matching its SHA256SUMS, and,
# when Finder laid it out, the window's settings and background in place.
MOUNT=$(mktemp -d)
hdiutil attach -quiet -nobrowse -readonly -mountpoint "$MOUNT" "$DMG"
detach() { hdiutil detach -quiet "$MOUNT" 2>/dev/null || hdiutil detach -quiet -force "$MOUNT"; rmdir "$MOUNT" 2>/dev/null || true; }
if [[ "$(ls "$MOUNT" | tr '\n' '|')" != "Applications|KMRP Installer.app|" ||
      "$(readlink "$MOUNT/Applications")" != /Applications ]]; then
    print -u2 "the disk image's root is not the app and the Applications link: $(ls "$MOUNT")"; detach; exit 1
fi
if ! codesign --verify --strict "$MOUNT/KMRP Installer.app" ||
   ! (cd "$MOUNT/KMRP Installer.app/Contents/Resources/kmrp" && shasum -a 256 -s -c SHA256SUMS); then
    print -u2 "the app in the disk image does not verify"; detach; exit 1
fi
if (( styled )) && ! { [[ -f "$MOUNT/.background/background.tiff" && -f "$MOUNT/.DS_Store" ]] &&
                       grep -q icvp "$MOUNT/.DS_Store"; }; then
    print -u2 "the disk image's window settings are missing"; detach; exit 1
fi
detach
ls -la "$DMG"
shasum -a 256 "$DMG"
