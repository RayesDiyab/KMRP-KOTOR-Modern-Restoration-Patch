#!/bin/zsh
# KMRP for macOS -- installer, uninstaller and status.
#
#   kmrp-mac.sh install   [--game "<path>/Knights of the Old Republic.app"] [--no-map-notes]
#                         [--resolution native|half | --size <W>x<H>] [--yes]
#   kmrp-mac.sh uninstall [--game ...] [--yes]
#   kmrp-mac.sh status    [--game ...]
#
# What install does, and what uninstall reverses (see macos/README.md):
#   1. Checks the game is the Steam Aspyr build it was made for (KOTOR_Exe 1.4.0,
#      SHA-256 C1FCB8D3...6D71) and is not running. Anything else is refused.
#   2. Copies KOTOR_Exe aside, then installs the engine the way KotOR Patch Manager does:
#      KotorPatcher.dylib, patches/ and patch_config.toml next to KOTOR_Exe, one
#      LC_LOAD_DYLIB for @executable_path/KotorPatcher.dylib, and an ad-hoc re-signature.
#      The patches: the widescreen patch KMRP runs on (with KMRP's engine fixes), KMRP's
#      layout patch, and the map-note corrections.
#   3. Picks the resolution: the display's size, and on a Retina display native (every pixel,
#      e.g. 3024x1964) or half (the point size, e.g. 1512x982, which macOS scales up). Writes
#      UseGuiFileLayouts=1, ForceWidth and ForceHeight to [Graphics Options] in swkotor.ini,
#      and, beside it, kmrp-controller.ini with the controller's default settings unless the
#      player already has one.
#   4. Installs into Contents/Assets/override KMRP's artwork and the menu set for that
#      resolution, the same files the Windows installer writes for it: from the pooled sets in
#      layouts.zip, or, for a size the build has no set for, .gui files blended by
#      kmrp-guiblend with the fonts and art of the nearest set. Then makes, from the player's
#      own game, what KMRP builds from the game's art and data: the hex row frames, the tutorial
#      popup's icons and tutorial.2da (kmrp-gameart), and the enlarged feat, power and skill
#      icons (kmrp-abilityicons). No release carries anything of the game's. Bundled
#      third-party art yields to a file already there; KMRP's own files replace one after
#      copying it aside.
#   5. Records every file and INI value it wrote in a manifest outside the game folder
#      (~/Library/Application Support/KMRP), so uninstall touches only what is still ours.
set -euo pipefail

VERSION_FILE="${0:A:h}/VERSION"
KMRP_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo unknown)
PAYLOAD="${0:A:h}"
STATE_ROOT="$HOME/Library/Application Support/KMRP"
STATE="$STATE_ROOT/macos"
VANILLA_EXE_SHA="c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71"
LOADER="@executable_path/KotorPatcher.dylib"
INI="$HOME/Library/Application Support/Knights of the Old Republic/swkotor.ini"
SETTINGS="${INI:h}/kmrp-controller.ini"

GAME=""
MAP_NOTES=1
RESOLUTION=""
SIZE=""
ASSUME_YES=0
BACKUP_SEQ=0
INSTALLING=0
WORK=""

say()  { print -r -- "$*"; }
warn() { print -r -- "warning: $*" >&2; }
die()  { print -r -- "error: $*" >&2; exit 1; }
sha()  { shasum -a 256 "$1" | cut -d' ' -f1; }

confirm() {
    (( ASSUME_YES )) && return 0
    local answer
    read -r "answer?$1 [y/N] " || return 1
    [[ "$answer" == [yY]* ]]
}

# ---------------------------------------------------------------------- locating the game
steam_libraries() {
    local steam="$HOME/Library/Application Support/Steam"
    print -r -- "$steam"
    local vdf="$steam/steamapps/libraryfolders.vdf"
    [[ -f "$vdf" ]] || return 0
    # "path"		"/Volumes/Games/SteamLibrary"
    sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)"[[:space:]]*$/\1/p' "$vdf"
}

find_game() {
    if [[ -n "$GAME" ]]; then
        [[ -d "$GAME/Contents/MacOS" ]] || die "not a game bundle: $GAME"
        return
    fi
    local lib
    for lib in ${(f)"$(steam_libraries)"}; do
        local candidate="$lib/steamapps/common/swkotor/Knights of the Old Republic.app"
        if [[ -x "$candidate/Contents/MacOS/KOTOR_Exe" ]]; then
            GAME="$candidate"
            return
        fi
    done
    die "KOTOR was not found in any Steam library. Pass --game \"/path/to/Knights of the Old Republic.app\"."
}

set_paths() {
    MACOS="$GAME/Contents/MacOS"
    EXE="$MACOS/KOTOR_Exe"
    OVERRIDE="$GAME/Contents/Assets/override"
    TEXTURE_PACK="$GAME/Contents/Assets/TexturePacks/swpc_tex_gui.erf"
    CHITIN_KEY="$GAME/Contents/Assets/chitin.key"
}

refuse_if_running() {
    if pgrep -f "Contents/MacOS/KOTOR_Exe" >/dev/null 2>&1; then
        die "KOTOR is running. Quit the game first."
    fi
}

# ---------------------------------------------------------------------- swkotor.ini
# The widescreen patch reads its settings from [Graphics Options]. The game keeps keys it does
# not know when it rewrites the file on quit (tested 2026-09-29), and writes CRLF line ends.
ini_value() {
    [[ -f "$INI" ]] || return 0
    tr -d '\r' < "$INI" | awk -v key="$1" '
        /^[ \t]*\[/ { in_gfx = (tolower($0) ~ /^[ \t]*\[graphics options\]/); next }
        in_gfx {
            split($0, kv, "=")
            k = kv[1]; gsub(/^[ \t]+|[ \t]+$/, "", k)
            if (tolower(k) == tolower(key)) { v = substr($0, index($0, "=") + 1); gsub(/^[ \t]+|[ \t]+$/, "", v); print v; exit }
        }'
}

ini_edit() {   # ini_edit set <key> <value> | ini_edit delete <key>
    local mode=$1 key=$2 value=${3:-}
    if [[ ! -f "$INI" ]]; then
        [[ "$mode" == set ]] || return 0
        mkdir -p "${INI:h}"
        : > "$INI"
    fi
    # Two passes over the file: the first finds out whether the key is already in the
    # section, the second rewrites it in place, or adds it under the section header (adding
    # the section at the end if there is none). Other lines are copied as they are.
    awk -v mode="$mode" -v key="$key" -v val="$value" '
        function bare(s) { sub(/\r$/, "", s); return s }
        function is_header(s) { return bare(s) ~ /^[ \t]*\[/ }
        function is_gfx(s) { return tolower(bare(s)) ~ /^[ \t]*\[graphics options\]/ }
        function key_of(s,   k) {
            s = bare(s); if (index(s, "=") == 0) return ""
            k = substr(s, 1, index(s, "=") - 1); gsub(/^[ \t]+|[ \t]+$/, "", k); return tolower(k)
        }
        BEGIN { k = tolower(key); eol = "\r\n" }
        NR == FNR {
            if (FNR == 1 && $0 !~ /\r$/) eol = "\n"
            if (is_header($0)) scan_gfx = is_gfx($0)
            else if (scan_gfx && key_of($0) == k) found = 1
            next
        }
        is_header($0) {
            in_gfx = is_gfx($0); printf "%s\n", $0
            if (in_gfx) { seen = 1; if (mode == "set" && !found) printf "%s=%s%s", key, val, eol }
            next
        }
        in_gfx && key_of($0) == k {
            if (mode == "set" && !written) { printf "%s=%s%s", key, val, eol; written = 1 }
            next
        }
        { printf "%s\n", $0 }
        END { if (mode == "set" && !seen) printf "[Graphics Options]%s%s=%s%s", eol, key, val, eol }
    ' "$INI" "$INI" > "$INI.kmrp-tmp"
    mv -f "$INI.kmrp-tmp" "$INI"
}

# ---------------------------------------------------------------------- resolution
display_geometry() {
    # The main display's size in points and in pixels, "pw ph xw xh": the calls the
    # widescreen patch makes (CGDisplayBounds, CGDisplayModeGetPixelWidth/Height). A Retina
    # display has twice as many pixels as points. system_profiler is only a fallback: it
    # omits the "UI Looks like" point size while the display sleeps.
    local g
    g=$(osascript -l JavaScript -e 'ObjC.import("CoreGraphics"); var d = $.CGMainDisplayID(); var b = $.CGDisplayBounds(d).size; var m = $.CGDisplayCopyDisplayMode(d); [b.width, b.height, $.CGDisplayModeGetPixelWidth(m), $.CGDisplayModeGetPixelHeight(m)].join(" ")' 2>/dev/null) || g=""
    if [[ "$g" == <->" "<->" "<->" "<-> ]]; then print -r -- "$g"; return; fi
    system_profiler SPDisplaysDataType 2>/dev/null | awk '
        /Resolution:/     { res = $0; ui = "" }
        /UI Looks like:/  { ui = $0 }
        /Main Display: Yes/ { exit }
        END {
            if (!match(res, /[0-9]+ x [0-9]+/)) exit
            split(substr(res, RSTART, RLENGTH), px, " x ")
            pw = px[1]; ph = px[2]
            if (ui != "" && match(ui, /[0-9]+ x [0-9]+/)) { split(substr(ui, RSTART, RLENGTH), pt, " x "); w = pt[1]; h = pt[2] }
            else if (res ~ /Retina/) { w = int(pw / 2); h = int(ph / 2) }
            else { w = pw; h = ph }
            print w, h, pw, ph
        }'
}

# Sets WIDTH and HEIGHT: the display's pixel size (native) or point size (half). On a display
# with no more pixels than points there is nothing to choose. Asks, unless --resolution or
# --yes (native) decides. --size sets them directly (another display, or a window size).
choose_resolution() {
    if [[ -n "$SIZE" ]]; then
        WIDTH=${SIZE%x*}; HEIGHT=${SIZE#*x}; RESOLUTION=size
        return
    fi
    local geo=(${=$(display_geometry)})
    (( ${#geo} >= 4 && geo[1] >= 640 && geo[2] >= 480 )) || die "could not read the display's size"
    if (( geo[3] <= geo[1] )); then
        RESOLUTION=native
    elif [[ -z "$RESOLUTION" ]] && (( ! ASSUME_YES )); then
        say "Resolution on this display:"
        say "  1) Native  ${geo[3]}x${geo[4]}  every pixel of the screen, the sharpest"
        say "  2) Half    ${geo[1]}x${geo[2]}  macOS scales it up, lighter on the GPU"
        local answer
        read -r "answer?Choose 1 or 2 [1]: " || answer=""
        case "$answer" in
            2*) RESOLUTION=half ;;
            ""|1*) RESOLUTION=native ;;
            *) die "not a choice: $answer" ;;
        esac
    fi
    [[ -n "$RESOLUTION" ]] || RESOLUTION=native
    if [[ "$RESOLUTION" == native ]]; then WIDTH=${geo[3]}; HEIGHT=${geo[4]}; else WIDTH=${geo[1]}; HEIGHT=${geo[2]}; fi
}

# ---------------------------------------------------------------------- menu sets
# layouts.zip is the pool the Windows installer embeds (tools/pack_resolution_layouts.py):
# index/<W>x<H>.txt lists a resolution's files as "<Override name><TAB><object>", and
# objects/<object> holds each distinct file once, named by the first 16 hex digits of its
# SHA-256.
listed_sizes() {
    unzip -Z1 "$PAYLOAD/layouts.zip" 'index/*' 2>/dev/null | sed -n 's|^index/\([0-9]*x[0-9]*\)\.txt$|\1|p'
}

# The listed size nearest WIDTHxHEIGHT: the nearest height (the fonts are baked at
# max(1, H / 720)), then the nearest shape.
nearest_size() {
    listed_sizes | awk -F x -v W="$WIDTH" -v H="$HEIGHT" '
        { dh = $2 - H; if (dh < 0) dh = -dh; da = $1 / $2 - W / H; if (da < 0) da = -da
          if (best == "" || dh < bh || (dh == bh && da < ba)) { best = $0; bh = dh; ba = da } }
        END { print best }'
}

# Extracts a listed size's files into <dir> under their Override names, and checks each against
# its object name.
extract_set() {   # extract_set <WxH> <dir>
    local size=$1 dir=$2 index="$WORK/index-$1.txt" name object
    unzip -p "$PAYLOAD/layouts.zip" "index/$size.txt" | tr -d '\r' > "$index"
    mkdir -p "$WORK/objects" "$dir"
    cut -f2 "$index" | sort -u | sed 's|^|objects/|' | xargs unzip -q -o "$PAYLOAD/layouts.zip" -d "$WORK"
    while IFS=$'\t' read -r name object; do
        [[ "$(sha "$WORK/objects/$object" | cut -c1-16)" == "${(L)object}" ]] || die "layouts.zip: $object does not match its name"
        cp "$WORK/objects/$object" "$dir/$name"
    done < "$index"
}

# ---------------------------------------------------------------------- manifest
# One line per file KMRP wrote: kind<TAB>absolute path<TAB>sha256 as written<TAB>backup name
#   added    -- did not exist before; uninstall deletes it if unchanged
#   replaced -- existed before; the original is in backup/, uninstall restores it if ours is unchanged
#   exe      -- KOTOR_Exe; backup/KOTOR_Exe is the original
#   dir      -- a directory KMRP created; removed if empty
#   ini      -- a swkotor.ini key (path column), the value written, the value before or "-";
#               uninstall puts the old value back if the key still holds KMRP's
#   settings -- kmrp-controller.ini, written because it was absent; the player's to edit, so
#               uninstall deletes it if unchanged and otherwise keeps it without complaint
record() { print -r -- "$1	$2	$3	$4" >> "$STATE/manifest.tsv"; }

set_ini() {   # set_ini <key> <value>: writes it and records what it replaced
    local before
    before=$(ini_value "$1")
    [[ "$before" == "$2" ]] && return 0
    ini_edit set "$1" "$2"
    record ini "$1" "$2" "${before:--}"
}

# The controller's settings (rumble), read by kmrp-controller.dylib while the game runs. As on
# Windows (KmrpPatcher.cs, DefaultSettings, whose values these are): written only when there
# is none, an existing copy is the player's and is never replaced, and uninstall removes it
# only if it is still exactly as written. Only the log's location differs.
install_settings() {
    if [[ -e "$SETTINGS" ]]; then
        say "Kept your ${SETTINGS:t}."
        return 0
    fi
    mkdir -p "${SETTINGS:h}"
    cat > "$SETTINGS" <<'EOF'
; KMRP controller settings. Read by the controller module while the game runs;
; changes take effect within a second, no restart needed.
[Rumble]
; Off, Original (BioWare's shipped rumble only) or Enhanced (adds KMRP's haptics)
Mode=Enhanced
; 0 to 100 percent
Strength=100
; the lightsaber hum, 0 to 100 percent of BioWare's level (0 turns it off);
; 6 is the weakest an Xbox pad can play
SaberHum=6
; the hum pulses: on for SaberHumPulseMs (0 = a steady hum), then off until
; the next pulse -- a gap picked at random between SaberHumPeriodMinMs and
; SaberHumPeriodMaxMs, afresh for every pulse (make them equal for a fixed rhythm)
SaberHumPulseMs=100
SaberHumPeriodMinMs=500
SaberHumPeriodMaxMs=2000
; 1 writes every rumble event to ~/Library/Logs/KMRP/rumble.log
Debug=0
EOF
    record settings "$SETTINGS" "$(sha "$SETTINGS")" "-"
}

bundled_art() {
    grep -qixF -- "${1:t}" "$PAYLOAD/bundled-override.txt" 2>/dev/null
}

# A texture resolves by resref: KOTOR prefers .tpc over .tga, so the other extension counts too.
texture_present() {
    local target=$1
    [[ -e "$target" ]] && return 0
    case "${target:e:l}" in
        tga) [[ -e "${target:r}.tpc" || -e "${target:r}.TPC" ]] ;;
        tpc) [[ -e "${target:r}.tga" || -e "${target:r}.TGA" ]] ;;
        *) return 1 ;;
    esac
}

install_file() {   # install_file <source> <destination directory>
    local src=$1 dir=$2 name=${1:t} target="$2/${1:t}" backup_name="-"
    # A name written twice would back up KMRP's own first copy as "the original", and
    # uninstall would restore it (the Windows installer hit this with i_checkbox01.tga). The
    # file system ignores case, so the check does too.
    if grep -qiF -- "	$target	" "$STATE/manifest.tsv"; then
        die "the package installs $name twice"
    fi
    if [[ -e "$target" ]]; then
        BACKUP_SEQ=$(( BACKUP_SEQ + 1 ))
        backup_name="$(printf %05d $BACKUP_SEQ)-$name"
        cp -p "$target" "$STATE/backup/$backup_name"
        cp -f "$src" "$target"
        record replaced "$target" "$(sha "$target")" "$backup_name"
    else
        cp "$src" "$target"
        record added "$target" "$(sha "$target")" "-"
    fi
}

# ---------------------------------------------------------------------- install
do_install() {
    find_game; set_paths; refuse_if_running
    [[ -f "$PAYLOAD/SHA256SUMS" ]] || die "the package is incomplete (SHA256SUMS missing)"
    say "KMRP $KMRP_VERSION for macOS"
    say "Game: $GAME"

    say "Checking the package..."
    (cd "$PAYLOAD" && shasum -a 256 -s -c SHA256SUMS) || die "the package is damaged: a file does not match SHA256SUMS. Download it again."

    if [[ -d "$STATE" ]]; then
        die "KMRP is already installed (state in $STATE). Run uninstall first."
    fi
    local exe_sha; exe_sha=$(sha "$EXE")
    if [[ "$exe_sha" != "$VANILLA_EXE_SHA" ]]; then
        die "KOTOR_Exe is not the unmodified Steam build this KMRP supports (SHA-256 $exe_sha, expected ${VANILLA_EXE_SHA[1,16]}...). If another patch is installed, remove it first; Steam's 'Verify integrity of game files' restores the original."
    fi
    local kpm_file
    for kpm_file in KotorPatcher.dylib patch_config.toml patches; do
        [[ -e "$MACOS/$kpm_file" ]] && die "KotOR Patch Manager files are already in the game ($MACOS/$kpm_file). KMRP installs the widescreen patch itself, in the version with KMRP's engine fixes; remove the patches in KPM first."
    done
    [[ -f "$TEXTURE_PACK" ]] || die "the game's texture pack is missing: $TEXTURE_PACK"

    choose_resolution
    local size="${WIDTH}x${HEIGHT}" from derived=0
    if listed_sizes | grep -qx "$size"; then
        from=$size
    else
        from=$(nearest_size)
        [[ -n "$from" ]] || die "layouts.zip lists no menu sets"
        derived=1
    fi
    say "Resolution: $size$([[ $RESOLUTION == half ]] && echo ' (scaled up by macOS)')"
    if (( derived )); then
        say "Menus: KMRP's layout blended for $size (the build has no set for it); fonts and art from $from"
    else
        say "Menus: KMRP's $size set"
    fi
    say "Map note corrections: $([[ $MAP_NOTES == 1 ]] && echo on || echo off)"
    confirm "Install KMRP into this game?" || die "cancelled"

    mkdir -p "$STATE/backup"
    : > "$STATE/manifest.tsv"
    # Written first, so an install that is interrupted in a way no trap can catch (power
    # loss, kill -9) still leaves uninstall enough to undo it.
    print -r -- "game=$GAME" > "$STATE/install.info"
    print -r -- "complete=0" >> "$STATE/install.info"
    # From here on, leaving before the end for any reason (an error, die, Ctrl-C) rolls
    # back what was already done.
    INSTALLING=1
    WORK=$(mktemp -d "${TMPDIR:-/tmp}/kmrp-install.XXXXXX")

    say "Preparing the menu set..."
    extract_set "$from" "$WORK/set"
    if (( derived )); then
        # The set whose fonts are installed: its caption width fits the Container and its
        # caption font lays out the Controller Layout screen for this size.
        "$PAYLOAD/bin/kmrp-guiblend" "$PAYLOAD/gui-blend.bin" "$WIDTH" "$HEIGHT" "$WORK/blend" \
            "$WORK/set" >/dev/null ||
            die "kmrp-guiblend could not blend $size"
        local gui
        for gui in "$WORK/blend"/*.gui(N); do
            cp -f "$gui" "$WORK/set/${gui:t}"
        done
    fi

    say "Backing up KOTOR_Exe..."
    cp -p "$EXE" "$STATE/backup/KOTOR_Exe"
    [[ "$(sha "$STATE/backup/KOTOR_Exe")" == "$VANILLA_EXE_SHA" ]] || die "the backup copy does not match"

    say "Installing the engine patches..."
    install_file "$PAYLOAD/engine/KotorPatcher.dylib" "$MACOS"
    mkdir "$MACOS/patches"; record dir "$MACOS/patches" "-" "-"
    install_file "$PAYLOAD/engine/patches/k1widescreenpatch.dylib" "$MACOS/patches"
    install_file "$PAYLOAD/engine/patches/kmrp-layout.dylib" "$MACOS/patches"
    install_file "$PAYLOAD/engine/patches/kmrp-controller.dylib" "$MACOS/patches"
    install_file "$PAYLOAD/engine/patches/kmrp-sdl3.dylib" "$MACOS/patches"
    if (( MAP_NOTES )); then
        install_file "$PAYLOAD/engine/patches/kmrp-map-notes.dylib" "$MACOS/patches"
        install_file "$PAYLOAD/engine/patch_config.toml" "$MACOS"
    else
        cp "$PAYLOAD/engine/patch_config.no-map-notes.toml" "$MACOS/patch_config.toml"
        record added "$MACOS/patch_config.toml" "$(sha "$MACOS/patch_config.toml")" "-"
    fi
    "$PAYLOAD/bin/kmrp-macho" add-dylib "$EXE" "$LOADER" >/dev/null
    codesign --force --sign - --identifier KOTOR_Exe "$EXE" 2>/dev/null
    codesign --verify "$EXE"
    "$PAYLOAD/bin/kmrp-macho" has-dylib "$EXE" KotorPatcher.dylib
    record exe "$EXE" "$(sha "$EXE")" "KOTOR_Exe"

    say "Setting the resolution in swkotor.ini..."
    set_ini UseGuiFileLayouts 1
    set_ini ForceWidth "$WIDTH"
    set_ini ForceHeight "$HEIGHT"
    install_settings

    say "Installing artwork and the menu set..."
    if [[ ! -d "$OVERRIDE" ]]; then
        mkdir -p "$OVERRIDE"; record dir "$OVERRIDE" "-" "-"
    fi
    local file skipped=0 count=0
    : > "$WORK/reserved.txt"
    for file in "$PAYLOAD"/override/*(.N) "$WORK/set"/*(.N); do
        print -r -- "${file:t}" >> "$WORK/reserved.txt"
        if bundled_art "$file" && texture_present "$OVERRIDE/${file:t}"; then
            skipped=$(( skipped + 1 )); continue
        fi
        install_file "$file" "$OVERRIDE"; count=$(( count + 1 ))
    done

    say "Making the row frames, tutorial icons and tutorial.2da from the game for $size..."
    local game_art=0
    if "$PAYLOAD/bin/kmrp-gameart" "$TEXTURE_PACK" "$CHITIN_KEY" "$HEIGHT" "$WORK/gameart" >/dev/null; then
        for file in "$WORK/gameart"/*(.N); do install_file "$file" "$OVERRIDE"; game_art=$(( game_art + 1 )); done
    else
        warn "the row frames, tutorial icons and tutorial.2da could not be made; the game keeps its own"
    fi

    say "Enlarging the feat, power and skill icons for $size..."
    local icons=0
    if "$PAYLOAD/bin/kmrp-abilityicons" "$TEXTURE_PACK" "$HEIGHT" "$WORK/icons" "$WORK/reserved.txt" >/dev/null; then
        for file in "$WORK/icons"/*.tga(N); do install_file "$file" "$OVERRIDE"; icons=$(( icons + 1 )); done
    else
        warn "the feat, power and skill icons could not be generated; they stay their original size"
    fi
    xattr -dr com.apple.quarantine "$MACOS" "$OVERRIDE" 2>/dev/null || true

    {
        print -r -- "version=$KMRP_VERSION"
        print -r -- "game=$GAME"
        print -r -- "installed=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        print -r -- "exe_before=$VANILLA_EXE_SHA"
        print -r -- "exe_after=$(sha "$EXE")"
        print -r -- "resolution=$size"
        print -r -- "resolution_choice=$RESOLUTION"
        print -r -- "menu_set=$([[ $derived == 1 ]] && echo "blended, fonts and art from $from" || echo "$from")"
        print -r -- "ability_icons=$icons"
        print -r -- "game_art=$game_art"
        print -r -- "map_notes=$MAP_NOTES"
        print -r -- "complete=1"
    } > "$STATE/install.info"
    INSTALLING=0
    rm -rf "$WORK"
    say "Installed: engine patches, $count Override files, $game_art files made from the game and $icons enlarged icons ($skipped bundled files left to mods already installed)."
    say "KOTOR_Exe was modified (one load command, re-signed ad hoc); the original is in $STATE/backup."
    say "To undo everything: run Uninstall KMRP.command, or kmrp-mac.sh uninstall."
}

# ---------------------------------------------------------------------- uninstall
rollback() {
    restore_from_manifest 1 || true
    rm -rf "$STATE"; rmdir "$STATE_ROOT" 2>/dev/null || true
    [[ -n "$WORK" ]] && rm -rf "$WORK"
    return 0
}

on_exit() {
    setopt localoptions noerrexit
    if (( INSTALLING )); then
        INSTALLING=0
        trap - ZERR
        warn "install did not finish; undoing what it had done"
        rollback
        warn "the game is as it was before"
    fi
}

restore_from_manifest() {   # restore_from_manifest <quiet>
    local quiet=${1:-0} kept=0 kind target recorded backup now
    [[ -f "$STATE/manifest.tsv" ]] || return 0
    # Newest first, so directories are removed after the files in them.
    while IFS=$'\t' read -r kind target recorded backup; do
        case "$kind" in
            exe)
                if [[ -f "$target" && "$(sha "$target")" == "$recorded" ]]; then
                    cp -p "$STATE/backup/$backup" "$target.kmrp-restore"
                    mv -f "$target.kmrp-restore" "$target"
                elif [[ -f "$target" && "$(sha "$target")" == "$VANILLA_EXE_SHA" ]]; then
                    :
                else
                    warn "KOTOR_Exe changed since KMRP installed it (a Steam update?); left as it is. The original is kept in $STATE/backup/KOTOR_Exe."
                    kept=$(( kept + 1 ))
                fi ;;
            added)
                if [[ -f "$target" && "$(sha "$target")" == "$recorded" ]]; then
                    rm -f "$target"
                elif [[ -e "$target" ]]; then
                    (( quiet )) || warn "changed since install, left in place: $target"
                    kept=$(( kept + 1 ))
                fi ;;
            settings)
                if [[ -f "$target" && "$(sha "$target")" == "$recorded" ]]; then
                    rm -f "$target"
                elif [[ -e "$target" ]]; then
                    (( quiet )) || say "Kept your edited ${target:t}."
                fi ;;
            replaced)
                if [[ -f "$target" && "$(sha "$target")" == "$recorded" ]]; then
                    cp -p "$STATE/backup/$backup" "$target"
                else
                    (( quiet )) || warn "changed since install, left in place (original kept in backup/$backup): $target"
                    kept=$(( kept + 1 ))
                fi ;;
            dir)
                rmdir "$target" 2>/dev/null || true ;;
            ini)
                now=$(ini_value "$target")
                if [[ "$now" == "$recorded" ]]; then
                    if [[ "$backup" == "-" ]]; then ini_edit delete "$target"; else ini_edit set "$target" "$backup"; fi
                elif [[ -n "$now" ]]; then
                    (( quiet )) || warn "swkotor.ini: $target is $now now, not what KMRP set; left as it is (it was ${backup/#-/unset} before)"
                fi ;;
        esac
    done < <(tail -r "$STATE/manifest.tsv")
    return $kept
}

do_uninstall() {
    [[ -f "$STATE/install.info" ]] || die "KMRP is not installed (no $STATE/install.info)."
    [[ -n "$GAME" ]] || GAME=$(sed -n 's/^game=//p' "$STATE/install.info")
    set_paths; refuse_if_running
    say "Removing KMRP from $GAME"
    confirm "Uninstall KMRP?" || die "cancelled"
    local kept=0
    restore_from_manifest 0 || kept=$?
    if (( kept == 0 )); then
        rm -rf "$STATE"
        rmdir "$STATE_ROOT" 2>/dev/null || true
        say "KMRP removed. KOTOR_Exe is back to $(sha "$EXE" | cut -c1-16)..."
    else
        say "KMRP removed, except $kept file(s) that changed after it installed them (listed above)."
        say "The backups are kept in $STATE."
    fi
}

# ---------------------------------------------------------------------- status
do_status() {
    if [[ -f "$STATE/install.info" ]]; then
        [[ -n "$GAME" ]] || GAME=$(sed -n 's/^game=//p' "$STATE/install.info")
        set_paths
        cat "$STATE/install.info"
        local total=0 changed=0 kind target recorded backup
        while IFS=$'\t' read -r kind target recorded backup; do
            case "$kind" in
                dir) continue ;;
                ini) say "swkotor.ini: $target=$(ini_value "$target") (KMRP set $recorded)"; continue ;;
                settings)
                    if [[ ! -f "$target" ]]; then say "${target:t}: removed (the defaults apply)"
                    elif [[ "$(sha "$target")" == "$recorded" ]]; then say "${target:t}: the defaults KMRP wrote"
                    else say "${target:t}: edited by you"; fi
                    continue ;;
            esac
            total=$(( total + 1 ))
            if [[ ! -f "$target" || "$(sha "$target")" != "$recorded" ]]; then changed=$(( changed + 1 )); fi
        done < "$STATE/manifest.tsv"
        say "files: $total recorded, $changed changed or missing since install"
        grep -qx "complete=1" "$STATE/install.info" || say "This install did not finish. Run uninstall to undo what it did."
    else
        find_game; set_paths
        say "KMRP is not installed."
        say "game: $GAME"
        [[ "$(sha "$EXE")" == "$VANILLA_EXE_SHA" ]] && say "KOTOR_Exe: unmodified Steam build (supported)" || say "KOTOR_Exe: modified or a different build"
        local geo=(${=$(display_geometry)})
        say "display: ${geo[1]}x${geo[2]} points, ${geo[3]}x${geo[4]} pixels"
        local candidate
        for candidate in "${geo[3]}x${geo[4]}" "${geo[1]}x${geo[2]}"; do
            if listed_sizes | grep -qx "$candidate"; then say "menu set for $candidate: in the package"
            else say "menu set for $candidate: blended at install (the package has no set for it)"; fi
        done
    fi
}

# ---------------------------------------------------------------------- main
[[ $# -ge 1 ]] || { sed -n '2,7p' "$0"; exit 2; }
command=$1; shift
while (( $# )); do
    case "$1" in
        --game) GAME=${2:?--game needs a path}; shift ;;
        --no-map-notes) MAP_NOTES=0 ;;
        --resolution)
            RESOLUTION=${2:?--resolution needs native or half}; shift
            [[ "$RESOLUTION" == (native|half) ]] || die "--resolution is native or half, not $RESOLUTION" ;;
        --size)
            SIZE=${2:?--size needs <width>x<height>}; shift
            [[ "$SIZE" == <->x<-> ]] && (( ${SIZE%x*} >= 640 && ${SIZE#*x} >= 480 )) ||
                die "--size is <width>x<height>, at least 640x480, not $SIZE" ;;
        --yes|-y) ASSUME_YES=1 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done
# Global, not inside do_install: zsh runs a trap set in a function when that function
# returns, and it must run when the shell exits mid-install. ZERR as well as EXIT: when
# errexit aborts on a failed command, zsh runs ZERR and exits without running EXIT
# (tested 2026-09-29); an explicit exit (die) runs EXIT.
trap 'on_exit' EXIT
trap 'on_exit' ZERR
trap 'exit 1' INT TERM
case "$command" in
    install) do_install ;;
    uninstall) do_uninstall ;;
    status) do_status ;;
    *) die "unknown command: $command (install, uninstall or status)" ;;
esac
