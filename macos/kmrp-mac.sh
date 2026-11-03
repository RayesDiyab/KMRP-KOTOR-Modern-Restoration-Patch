#!/bin/zsh
# KMRP for macOS -- installer, uninstaller and status.
#
#   kmrp-mac.sh install   [--game "<path>/Knights of the Old Republic.app"] [--no-map-notes] [--no-hd-icons] [--no-marked-empty]
#                         [--no-controller] [--high-fps | --no-high-fps] [--keep-anti-aliasing]
#                         [--debug-logs] [--no-prepare]
#                         [--resolution current|native | --size <W>x<H>] [--yes]
#   kmrp-mac.sh uninstall [--game ...] [--yes]
#   kmrp-mac.sh status    [--game ...] [--brief]
#
# --app-store with any of the three is about the Mac App Store's game (as is --game with that
# game's path, and install on a Mac with no Steam copy): KMRP is then an app of its own beside
# the game, "KOTOR with KMRP", and the game is not changed (the section "the Mac App Store's
# game" below, docs/macos-app-store.md).
#
# What install does, and what uninstall reverses (see macos/README.md):
#   1. Checks the game is the Steam Aspyr build it was made for (KOTOR_Exe 1.4.0,
#      SHA-256 C1FCB8D3...6D71) and is not running. Anything else is refused.
#   2. Copies KOTOR_Exe aside, then installs the engine the way KotOR Patch Manager does:
#      KotorPatcher.dylib, patches/ and patch_config.toml next to KOTOR_Exe, one
#      LC_LOAD_DYLIB for @executable_path/KotorPatcher.dylib, and an ad-hoc re-signature.
#      The patch: KMRP's one patch, FTD's widescreen patch and Stray Bug Fixes (KMRP's engine
#      fixes) with KMRP's layout code, the map-note corrections and the controller. An install
#      of FTD's patches through KPM is replaced (kpm_check, kpm_remove); with other KPM patches
#      installed, KMRP installs for KPM instead, leaving KOTOR_Exe and KPM's files alone. Leaves
#      KPM's own records (kpm_install_state.json, KOTOR_Exe.backup.<time>) and KMRP-macOS.kpatch in
#      KPM's patch folder, so KPM recognises the install, as on Windows.
#   3. Picks the resolution the game starts at: the display's size, and on a Retina display
#      native (every pixel, e.g. 3024x1964) or half (the point size, e.g. 1512x982, which macOS
#      scales up). Writes it as Width and Height to [Graphics Options] in swkotor.ini (a size
#      the display does not offer, given with --size, as ForceWidth and ForceHeight). In the
#      game, Options, Graphics changes it at any time. And, in a KMRP folder beside swkotor.ini,
#      KMRP/controller.ini with the controller's default settings unless the player already
#      has one (an older kmrp-controller.ini beside swkotor.ini is moved there).
#   4. Nothing goes into the game's override folder, since 2026-10-04: the menu set for every
#      resolution and KMRP's artwork were inside the patch's module (patches/kmrp-assets) until
#      2026-11-03, and are in the art pack patches/kmrp-assets.pack beside it since, which this
#      installer writes (SDL is the controller patch's, inside its module). The module
#      unpacks what the resolution needs to ~/Library/Caches/KMRP when the game starts,
#      blends a set for a size the build has none for, and makes from the player's own game
#      what KMRP builds from its art and data. Until then this installer did all of that and
#      wrote some 1,800 files into Contents/Assets/override.
#      Since 2026-11-03 the install makes that cache itself, once everything else is in place,
#      as Windows' installer does: the common files and the set of every size the display
#      offers that KMRP covers (prepare_art, bin/kmrp-prepare), so the game starts without
#      making anything. Not fatal: what is not made then, the game makes when it first starts at
#      that size. --no-prepare leaves all of it to the game. Uninstall removes the cache.
#   5. Records every file and INI value it wrote in a manifest outside the game folder
#      (~/Library/Application Support/KMRP), so uninstall touches only what is still ours.
set -euo pipefail

VERSION_FILE="${0:A:h}/VERSION"
KMRP_VERSION=$(cat "$VERSION_FILE" 2>/dev/null || echo unknown)
PAYLOAD="${0:A:h}"
STATE_ROOT="$HOME/Library/Application Support/KMRP"
STATE="$STATE_ROOT/macos"
VANILLA_EXE_SHA="c1fcb8d37c702849882a17751c63ee0af7c2b9cbbc3b31b98a5f0edbc27c6d71"
# The Mac App Store's game (bundle id com.aspyr.kotor, 1.4.1 build 199106, read 2026-10-12): the
# same game built without Steam's library, another KOTOR_Exe, every address of the patches
# another one there. It is not one KMRP can install into as it does into Steam's: on macOS 27
# the App Store game's launcher did not start once any file in the bundle had been added or
# changed (docs/macos-app-store.md). Supported since 2026-10-12 another way, by an app beside
# it (do_install_app_store).
APPSTORE_EXE_SHA="d03315aace822908d6b7ca936d47c644ffe6ebf79822c8c62225bfaaf79ad7ca"
APPSTORE_BUNDLE_ID="com.aspyr.kotor"
APPSTORE=0     # --app-store: this run is about the Mac App Store's game
LOADER="@executable_path/KotorPatcher.dylib"
INI="$HOME/Library/Application Support/Knights of the Old Republic/swkotor.ini"
# KMRP's own file in a KMRP folder of the game's settings folder, as Windows' KMRP\controller.ini
# (the maintainer, 2026-10-20: "we shouldnt clutter the folder like this"). The module moves an
# older kmrp-controller.ini there too, for a controller patch installed without this script.
SETTINGS="${INI:h}/KMRP/controller.ini"
OLD_SETTINGS="${INI:h}/kmrp-controller.ini"
ASPYR_PREFS="$HOME/Library/Preferences/com.aspyr.kotor.steam.plist"

GAME=""
MAP_NOTES=1
HD_ICONS=1       # --no-hd-icons: the patch's hd-icons option, the bundled HD icon pack (since 2026-10-08)
MARKED_EMPTY=1   # --no-marked-empty: the patch's marked-empty option, ShaeMyName's Marked Empty Containers
CONTROLLER=1   # controller support: its own patch, kmrp-controller, and its settings file (Windows' switch too)
HIGH_FPS=""    # High FPS Fixes for the Mac, a fifth patch: 1, 0, or unset for Windows' rule, on where the display runs above 60 Hz
KEEP_AA=0      # --keep-anti-aliasing: the game's Anti Aliasing setting is left as it is on a 4K display too
DEBUG_LOGS=0   # the module's diagnostic log (Windows' third option, off unless asked for)
PREPARE=1      # --no-prepare: the cache is left to the game's first start (prepare_art)
PREPARED=0     # how many resolutions prepare_art made, all of them with the common files; else 0
RESOLUTION=""
SIZE=""
ASSUME_YES=0
BRIEF=0   # status without checking each installed file (KMRP Installer's view)
BACKUP_SEQ=0
INSTALLING=0
ROLLING_BACK=0   # restore_from_manifest is undoing a failed install (rollback), not uninstalling
WORK=""
BIN=""

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

# A Mac App Store copy of the game: the usual places, then Spotlight by its bundle id. Prints
# its path, or nothing.
app_store_game() {
    local candidate
    for candidate in "/Applications/Knights of the Old Republic.app" "$HOME/Applications/Knights of the Old Republic.app" \
                     ${(f)"$(mdfind "kMDItemCFBundleIdentifier == '$APPSTORE_BUNDLE_ID'" 2>/dev/null)"}; do
        [[ -x "$candidate/Contents/MacOS/KOTOR_Exe" ]] || continue
        is_app_store_game "$candidate" && { print -r -- "$candidate"; return 0; }
    done
    return 1
}

is_app_store_game() {   # by its bundle id or its receipt, without hashing the executable
    local id
    id=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Contents/Info.plist" 2>/dev/null)
    [[ "$id" == "$APPSTORE_BUNDLE_ID" || -e "$1/Contents/_MASReceipt/receipt" ]]
}

find_game() {
    if [[ -n "$GAME" ]]; then
        [[ -d "$GAME/Contents/MacOS" ]] || die "not a game bundle: $GAME"
        is_app_store_game "$GAME" && APPSTORE=1
        return 0
    fi
    if (( APPSTORE )); then
        GAME=$(app_store_game) || die "KOTOR from the Mac App Store was not found in Applications."
        return 0
    fi
    local lib
    for lib in ${(f)"$(steam_libraries)"}; do
        local candidate="$lib/steamapps/common/swkotor/Knights of the Old Republic.app"
        if [[ -x "$candidate/Contents/MacOS/KOTOR_Exe" ]]; then
            GAME="$candidate"
            return
        fi
    done
    local store
    if store=$(app_store_game); then
        GAME=$store; APPSTORE=1
        return 0
    fi
    die "KOTOR was not found in any Steam library. Pass --game \"/path/to/Knights of the Old Republic.app\"."
}

set_paths() {
    MACOS="$GAME/Contents/MacOS"
    EXE="$MACOS/KOTOR_Exe"
    TEXTURE_PACK="$GAME/Contents/Assets/TexturePacks/swpc_tex_gui.erf"
    OPTIONS_INI="$MACOS/configs/kmrp.ini"
}

# This game, not any copy of it: another copy running elsewhere does not stop an install here.
refuse_if_running() {
    # Matched in the shell, not with `| grep -q`: under pipefail grep leaving at the first match
    # can kill the writer, and the pipeline then fails as if nothing matched.
    local line
    for line in ${(f)"$(ps -axo command= 2>/dev/null)"}; do
        if [[ "$line" == *"$EXE"* || "$line" == *"${EXE:A}"* ]]; then
            die "KOTOR is running. Quit the game first."
        fi
    done
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
    # For the installer's own test, which has to give the same answer on any Mac.
    if [[ "${KMRP_DISPLAY_GEOMETRY:-}" == <->" "<->" "<->" "<-> ]]; then print -r -- "$KMRP_DISPLAY_GEOMETRY"; return; fi
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

# The highest refresh rate the main display offers, in hertz; nothing when it cannot be told.
display_refresh() {
    osascript -l JavaScript -e 'ObjC.import("AppKit"); var s = $.NSScreen.mainScreen; s.respondsToSelector("maximumFramesPerSecond") ? s.maximumFramesPerSecond : 0' 2>/dev/null |
        grep -x '[0-9][0-9]*' || true
}

# High FPS Fix where it was not chosen: Windows' rule (KmrpSettings.HighFpsFixAuto), on for a
# display that reports more than 60 Hz; 59, 60 and 61 count as 60.
choose_high_fps() {
    [[ -n "$HIGH_FPS" ]] && return 0
    local rate; rate=$(display_refresh)
    if [[ -n "$rate" ]] && (( rate >= 62 )); then HIGH_FPS=1; else HIGH_FPS=0; fi
}

# Sets WIDTH and HEIGHT: the display's point size (half: the resolution macOS is set to) or
# pixel size (native). On a display with no more pixels than points there is nothing to
# choose. Asks, unless --resolution or --yes (half) decides. --size sets them directly (another display, or a window size).
choose_resolution() {
    if [[ -n "$SIZE" ]]; then
        WIDTH=${SIZE%x*}; HEIGHT=${SIZE#*x}; RESOLUTION=size
        return
    fi
    local geo=(${=$(display_geometry)})
    (( ${#geo} >= 4 && geo[1] >= 640 && geo[2] >= 480 )) || die "could not read the display's size"
    # The default is the resolution macOS is set to ("half", the display's size in points: the
    # "Looks like" size in System Settings → Displays), since 2026-10-01 (the maintainer: "I
    # want it to patch to the currently running resolution"); a player reading 1512x982 there
    # took 3024x1964 for a wrong guess. "native", every pixel of a Retina display, is the
    # other choice. Until then native was the default.
    if (( geo[3] <= geo[1] )); then
        RESOLUTION=native
    elif [[ -z "$RESOLUTION" ]] && (( ! ASSUME_YES )); then
        say "Resolution on this display:"
        say "  1) Current  ${geo[1]}x${geo[2]}  the resolution macOS is set to"
        say "  2) Retina   ${geo[3]}x${geo[4]}  every pixel of the screen: sharper, heavier on the GPU"
        local answer
        read -r "answer?Choose 1 or 2 [1]: " || answer=""
        case "$answer" in
            2*) RESOLUTION=native ;;
            ""|1*) RESOLUTION=half ;;
            *) die "not a choice: $answer" ;;
        esac
    fi
    [[ -n "$RESOLUTION" ]] || RESOLUTION=half
    if [[ "$RESOLUTION" == native ]]; then WIDTH=${geo[3]}; HEIGHT=${geo[4]}; else WIDTH=${geo[1]}; HEIGHT=${geo[2]}; fi
}

# ---------------------------------------------------------------------- menu sets
# sizes.txt lists the resolutions the build has a menu set of its own for, one <W>x<H> a line
# (the sets themselves are in the art pack, kmrp-assets.pack). For any other size the module blends one
# from the nearest set, when kmrp-guiblend's table covers the size.
listed_sizes() {
    tr -d '\r' < "$PAYLOAD/sizes.txt" 2>/dev/null | grep -E '^[0-9]+x[0-9]+$'
}

is_listed_size() {   # is_listed_size <WxH>: in the shell, not `| grep -qx` (pipefail, above)
    local sizes; sizes=$(listed_sizes || true)
    (( ${${(f)sizes}[(Ie)$1]} ))
}

# The listed size nearest WIDTHxHEIGHT: the nearest height (the fonts are baked at
# max(1, H / 720)), then the nearest shape.
nearest_size() {
    listed_sizes | awk -F x -v W="$WIDTH" -v H="$HEIGHT" '
        { dh = $2 - H; if (dh < 0) dh = -dh; da = $1 / $2 - W / H; if (da < 0) da = -da
          if (best == "" || dh < bh || (dh == bh && da < ba)) { best = $0; bh = dh; ba = da } }
        END { print best }'
}

# ---------------------------------------------------------------------- KotOR Patch Manager
# FTD's widescreen patch installed through KotOR Patch Manager, with the Stray Bug Fixes it
# requires. KMRP's own patch carries both (tools/make_kmrp_patch.py), so it replaces such an
# install instead of refusing it: FTD's files are deleted, as FTD agreed (2026-09-30), and the
# untouched game is put back from KPM's copy before KMRP installs. On the Mac KPM names
# KotorPatcher.dylib in KOTOR_Exe's load commands and leaves beside it the patch list, the
# patches folder, its install record and that copy, KOTOR_Exe.backup.<time>, with a .json of its
# details (KPatchCore: DeploymentPolicy's LinkedDependency, BackupManager, PatchRemover). FTD's
# modules are patches/<patch id>.dylib, and the ids do not change between his versions. Only an
# install of his two patches is replaced (the maintainer, 2026-10-01: that "should still work").
# With any other KPM patch installed, KMRP installs for KotOR Patch Manager instead, as the
# Windows installer does (src/patcher/KpmEdition.cs, ForeignRuntimeFile, since 2026-10-01; it
# refused until then): the menus, art and INI only, no runtime, no load command, KOTOR_Exe
# untouched, and KMRP-macOS.kpatch where KPM finds it, for the player to tick in KPM. KMRP's
# uninstall leaves the untouched game; FTD's patch is not put back.
#
# And KMRP's own install is one KPM recognises and takes over, as on Windows (KpmState,
# WriteKpmBackup, DeliverKpatches): kpm_install_state.json with the game's identity, a copy of
# the untouched KOTOR_Exe in KPM's format beside it, from which KPM's Apply starts, and
# KMRP-macOS.kpatch in KPM's patch folder. Uninstall leaves the runtime to KPM once KPM's Apply has
# rewritten patch_config.toml (Restore, ConfigChangedSinceInstall).
# addresses.db: KPM's Apply copies its address database beside the game (PatchApplicator) and
# its Remove deletes it (PatchRemover), as with the rest.
KPM_FILES=(KotorPatcher.dylib patch_config.toml patches kpm_install_state.json addresses.db)
KMRP_PACK=kmrp-assets.pack   # KMRP's art, beside KMRP's module in patches/ (no module itself)
FTD_PATCHES=(k1widescreenpatch k1-stray-bug-fixes-patch)
# What this installer installs, since 2026-10-04: KMRP's own patch and the two of FTD's it
# requires (until then KMRP's one patch carried a copy of them). The package's file for each and
# the patch's id, which is also the name KPM gives its module in patches/. In KPM's order: a patch
# after the ones it requires.
#
# Since 2026-10-07 controller support is a fourth patch, kmrp-controller, which works with or
# without KMRP and is installed while Controller Support is on (until then it was part of KMRP's
# patch, an option of it). KPATCH_FILES and KPATCH_IDS are what this install installs, set by
# choose_patches once the options are read; KMRP_IDS is every patch a KMRP install can hold, for
# telling an install that is only KMRP's.
# The two of KMRP's own are named for the Mac since 2026-10-08, as Windows' files are named
# KMRP.kpatch and "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch": the ids are the same on
# both systems and neither system's files run on the other. Until then they were kmrp.kpatch
# and kmrp-controller.kpatch (OLD_KPATCH_FILES, removed from KPM's folder when they are KMRP's).
KMRP_KPATCH="KMRP-macOS.kpatch"
PAD_KPATCH="KOTOR 1 Native Controller Mod + Xbox HUD (macOS).kpatch"
# Since 2026-10-08 a fifth, High FPS Fixes for the Mac (a port of D3M0's patch, whose id it
# keeps), installed while High FPS Fix is on: Windows installs D3M0's own the same way.
HFPS_KPATCH="High FPS Fixes (macOS).kpatch"
OLD_KPATCH_FILES=(kmrp.kpatch kmrp-controller.kpatch)
KPATCH_FILES=(K1StrayBugFixes.kpatch K1WidescreenPatch.kpatch "$KMRP_KPATCH" "$PAD_KPATCH" "$HFPS_KPATCH")
KPATCH_IDS=(k1-stray-bug-fixes-patch k1widescreenpatch kmrp kmrp-controller high-fps-fixes)
KMRP_IDS=($KPATCH_IDS)
choose_patches() {
    choose_high_fps
    if (( ! CONTROLLER )); then
        KPATCH_FILES=(${KPATCH_FILES:#$PAD_KPATCH})
        KPATCH_IDS=(${KPATCH_IDS:#kmrp-controller})
    fi
    if (( ! HIGH_FPS )); then
        KPATCH_FILES=(${KPATCH_FILES:#$HFPS_KPATCH})
        KPATCH_IDS=(${KPATCH_IDS:#high-fps-fixes})
    fi
    return 0
}
KPM_ORIGINAL=""   # the untouched game, when an install is to be replaced
KPM_PROBLEM=""    # why it cannot be, otherwise
KPM_OTHERS=""     # the other patches KPM has installed, when KMRP installs for KPM
KPATCH_FOLDER=""  # where KMRP-macOS.kpatch went
# KPM's identity for the game (KPatchCore GameDetector: Platform.macOS 1, Distribution.Steam 1,
# Architecture.x86_64 1, GameTitle.KOTOR1 1), in its upper-case hex.
KPM_VERSION_NAME="1 1.4.0 (Aspyr macOS)"
KPM_BUILD_IDENTITY="macho:05EFCB7E4FCB3536B278E10F812BB06C"
KPM_EXE_SIZE=6333424
# KPatchLauncher's settings (AppSettings: .NET's ApplicationData/KPatchLauncher/settings.json).
# On macOS .NET 8 gives ~/.config for ApplicationData; ~/Library/Application Support is read
# too, since that was not checked on a Mac when this was written.
KPM_SETTINGS=("$HOME/.config/KPatchLauncher/settings.json"
              "$HOME/Library/Application Support/KPatchLauncher/settings.json")

json_string() {   # a JSON string's contents
    local s=${1//\\/\\\\}
    s=${s//\"/\\\"}
    print -rn -- "$s"
}

kpm_patches_folder() {   # KPM's patch folder from its settings ("PatchesPath"), if it exists
    # Not `path`: in zsh that is $PATH, and a local one empties it.
    local file folder
    for file in $KPM_SETTINGS; do
        [[ -f "$file" ]] || continue
        folder=$(sed -n 's/.*"PatchesPath"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$file" | head -1)
        # System.Text.Json escapes characters outside ASCII as \uXXXX: such a path is not
        # read here, and the patch then goes where an install for KPM puts it without one.
        [[ -n "$folder" && "$folder" == /* && "$folder" != *\\* && -d "$folder" ]] || continue
        print -r -- "$folder"
        return 0
    done
    return 1
}

# Each read whole into the shell first: piped into `grep -q` under pipefail, grep leaving at the
# first match kills unzip, and a match then looks like none (for the Widescreen Patch's module,
# a usable patch would have been taken for one without the entry points and replaced).
kpatch_manifest_has() {   # kpatch_manifest_has <.kpatch> <line>
    local line
    for line in ${(f)"$(unzip -p "$1" manifest.toml 2>/dev/null || true)"}; do
        [[ "${line%$'\r'}" == "$2" ]] && return 0
    done
    return 1
}
kpatch_is_kmrp() { kpatch_manifest_has "$1" 'id = "kmrp"'; }
kpatch_is_controller() { kpatch_manifest_has "$1" 'id = "kmrp-controller"'; }
# The Mac port, not D3M0's own file for Windows, which has the same id.
kpatch_is_high_fps() { kpatch_manifest_has "$1" 'name = "High FPS Fixes (macOS)"'; }

# The Widescreen Patch KMRP needs has the entry points KMRP asks for its .gui mode by
# (K1Widescreen_UseGuiFileLayouts; FTD's patch has them from its 2026-10-04 adjustment). The
# module's printable runs, as text the shell can hold (the module has NUL bytes); tr, not
# strings, which a Mac without the command line tools does not have.
kpatch_has_entry_points() {
    local names
    names=$(unzip -p "$1" binaries/macos_x86_64.dylib 2>/dev/null | LC_ALL=C tr -cs '[:print:]' '\n' || true)
    [[ "$names" == *K1Widescreen_UseGuiFileLayouts* ]]
}

deliver_kpatch() {   # deliver_kpatch <for_kpm>: this install's .kpatch files into KPM's patch folder
    local folder file src target state
    if [[ ! -f "$PAYLOAD/engine/$KMRP_KPATCH" ]]; then
        warn "the package has no KMRP-macOS.kpatch; KotOR Patch Manager will not list KMRP"
        return 0
    fi
    if folder=$(kpm_patches_folder); then
        :
    elif (( $1 )); then
        # No KPM settings found: beside the game, for the player to add in KPM.
        folder="${GAME:h}/KPM patches"
        if [[ ! -d "$folder" ]]; then mkdir -p "$folder"; record dir "$folder" "-" "-"; fi
    else
        return 0
    fi
    # A patch file under its name of before 2026-10-08, of the same id as one delivered now:
    # KPM would list the patch twice. Removed when it is KMRP's; anyone else's file is left.
    for file in $OLD_KPATCH_FILES; do
        target="$folder/$file"
        [[ -f "$target" ]] || continue
        if kpatch_is_kmrp "$target" || kpatch_is_controller "$target"; then rm -f "$target"; fi
    done
    for file in $KPATCH_FILES; do
        src="$PAYLOAD/engine/$file"; target="$folder/$file"; state=created
        [[ -f "$src" ]] || continue
        if [[ -e "$target" ]]; then
            [[ "$(sha "$target")" == "$(sha "$src")" ]] && continue   # already there: not KMRP's to remove
            case "$file" in
                "$KMRP_KPATCH")
                    if ! kpatch_is_kmrp "$target"; then warn "left $target alone: it is not KMRP's"; continue; fi
                    state=replaced ;;   # an older KMRP's: brought up to this version, and left at uninstall
                "$PAD_KPATCH")
                    if ! kpatch_is_controller "$target"; then warn "left $target alone: it is not KMRP's controller patch"; continue; fi
                    state=replaced ;;
                "$HFPS_KPATCH")
                    if ! kpatch_is_high_fps "$target"; then warn "left $target alone: it is not the Mac's High FPS Fixes"; continue; fi
                    state=replaced ;;
                K1WidescreenPatch.kpatch)
                    # FTD's own file. One KMRP can work with stays; one from before the entry
                    # points is copied aside and replaced, and put back at uninstall.
                    if kpatch_has_entry_points "$target"; then continue; fi
                    cp -p "$target" "$STATE/backup/$file"
                    state="swapped" ;;
                *)  continue ;;         # FTD's Stray Bug Fixes, whatever its version: left as it is
            esac
        fi
        cp -f "$src" "$target"
        record kpatch "$target" "$(sha "$target")" "$state"
    done
    KPATCH_FOLDER=$folder
}

kpm_patch_list() {   # the installed patches' ids, as a JSON array's contents
    local id list=""
    for id in $KPATCH_IDS; do list+="${list:+, }\"$id\""; done
    print -rn -- "$list"
}

write_kpm_backup() {   # KOTOR_Exe as KPM backs it up (BackupManager, BackupInfo), before it changes
    local stamp name now
    stamp=$(date +%Y%m%d_%H%M%S); now=$(date +%Y-%m-%dT%H:%M:%S)
    name="KOTOR_Exe.backup.$stamp"
    [[ ! -e "$MACOS/$name" ]] || die "$MACOS/$name is in the way"
    cp -p "$EXE" "$MACOS/$name"
    [[ "$(sha "$MACOS/$name")" == "$VANILLA_EXE_SHA" ]] || die "the copy of KOTOR_Exe for KotOR Patch Manager does not match"
    record added "$MACOS/$name" "$VANILLA_EXE_SHA" "-"
    {
        print -r -- '{'
        print -r -- "  \"OriginalPath\": \"$(json_string "$EXE")\","
        print -r -- "  \"BackupPath\": \"$(json_string "$MACOS/$name")\","
        print -r -- "  \"Hash\": \"${(U)VANILLA_EXE_SHA}\","
        print -r -- "  \"FileSize\": $KPM_EXE_SIZE,"
        print -r -- "  \"CreatedAt\": \"$now\","
        print -r -- '  "DetectedVersion": null,'
        print -r -- "  \"InstalledPatches\": [$(kpm_patch_list)]"
        print -r -- '}'
    } > "$MACOS/$name.json"
    record added "$MACOS/$name.json" "$(sha "$MACOS/$name.json")" "-"
}

write_kpm_state() {   # kpm_install_state.json (ManagedInstallState, schema 1)
    local now hash=${(U)VANILLA_EXE_SHA}
    now=$(date +%Y-%m-%dT%H:%M:%S)
    {
        print -r -- '{'
        print -r -- '  "SchemaVersion": 1,'
        print -r -- "  \"GameExePath\": \"$(json_string "$EXE")\","
        print -r -- '  "GameExeFileName": "KOTOR_Exe",'
        print -r -- "  \"OriginalHash\": \"$hash\","
        print -r -- "  \"OriginalFileSize\": $KPM_EXE_SIZE,"
        print -r -- '  "OriginalVersion": {'
        print -r -- '    "Platform": 1,'
        print -r -- '    "Distribution": 1,'
        print -r -- "    \"Version\": \"$KPM_VERSION_NAME\","
        print -r -- '    "Architecture": 1,'
        print -r -- '    "Title": 1,'
        print -r -- "    \"FileSize\": $KPM_EXE_SIZE,"
        print -r -- "    \"Hash\": \"$hash\","
        print -r -- "    \"BuildIdentity\": \"$KPM_BUILD_IDENTITY\""
        print -r -- '  },'
        print -r -- '  "CurrentHash": null,'
        print -r -- '  "CurrentFileSize": null,'
        print -r -- "  \"InstalledPatches\": [$(kpm_patch_list)],"
        print -r -- '  "LibraryProxyInstalled": false,'
        print -r -- '  "LinkedDependencyInstalled": true,'
        print -r -- "  \"CreatedAt\": \"$now\","
        print -r -- "  \"UpdatedAt\": \"$now\""
        print -r -- '}'
    } > "$MACOS/kpm_install_state.json"
    record added "$MACOS/kpm_install_state.json" "$(sha "$MACOS/kpm_install_state.json")" "-"
}

is_runtime_path() {   # KPM's runtime as KMRP's install laid it out, which KPM takes over
    case "${1:t}" in
        KotorPatcher.dylib|patch_config.toml|kpm_install_state.json|KOTOR_Exe|KOTOR_Exe.backup.*) return 0 ;;
    esac
    # The options KPM's Apply records for the patches it installed are KPM's as well.
    [[ "${1:h}" == "${OPTIONS_INI:h}" || "$1" == "${OPTIONS_INI:h}" ]] && return 0
    [[ "${1:h}" == "$MACOS/patches" || "$1" == "$MACOS/patches" ]]
}

kpm_backups() {   # KPM's copies of the game and their .json, newest first
    print -rl -- "$MACOS"/KOTOR_Exe.backup.*(Nom)
}

kpm_present() {   # 0 when KotOR Patch Manager left anything beside KOTOR_Exe
    local f
    for f in $KPM_FILES; do
        # A patches folder holding only KMRP's art pack is KMRP's leftover (lone_pack), not KPM's.
        [[ "$f" == patches ]] && lone_pack && continue
        [[ -e "$MACOS/$f" ]] && return 0
    done
    [[ -n "$(kpm_backups)" ]]
}

# KMRP's module still installed by someone: KotOR Patch Manager's list naming KMRP's patch, or its
# module in patches/. While it is, the art pack beside it is what it reads, and stays.
kmrp_module_remains() {
    [[ -e "$MACOS/patches/kmrp.dylib" ]] && return 0
    [[ -f "$MACOS/patch_config.toml" ]] || return 1
    local id
    for id in ${(f)"$(sed -n 's/^id = "\(.*\)"$/\1/p' "$MACOS/patch_config.toml")"}; do
        [[ "$id" == kmrp ]] && return 0
    done
    return 1
}

# patches/ holding KMRP's art pack and nothing else: left by an install of KMRP that KotOR Patch
# Manager took over beside other patches, once KPM's Apply took KMRP's module out (KPM removes
# modules only). KMRP's own leftover, which nothing reads: never taken for an install of KPM's.
lone_pack() {
    local entries=("$MACOS"/patches/*(DN))
    (( ${#entries} == 1 )) && [[ "${entries[1]:t}" == "$KMRP_PACK" ]] && ! kmrp_module_remains
}

kpm_check() {   # 0: FTD's install, replaced (KPM_ORIGINAL); 2: others', installed for (KPM_OTHERS);
                # 1: FTD's alone but not replaceable (KPM_PROBLEM)
    KPM_ORIGINAL="" KPM_PROBLEM="" KPM_OTHERS=""
    local id module backup others=()
    if [[ -f "$MACOS/patch_config.toml" ]]; then
        for id in ${(f)"$(sed -n 's/^id = "\(.*\)"$/\1/p' "$MACOS/patch_config.toml")"}; do
            (( ${FTD_PATCHES[(Ie)$id]} )) || others+=$id
        done
    fi
    for module in "$MACOS"/patches/*(N); do
        [[ "$module" == *.pack ]] && continue   # KMRP's art, no module
        (( ${FTD_PATCHES[(Ie)${module:t:r}]} )) || others+=${module:t}
    done
    if (( ${#others} )); then
        KPM_OTHERS="${(j:, :)${(u)others}}"
        return 2
    fi
    if [[ "$(sha "$EXE")" == "$VANILLA_EXE_SHA" ]]; then KPM_ORIGINAL=$EXE; return 0; fi
    for backup in ${(f)"$(kpm_backups)"}; do
        [[ "$backup" == *.json ]] && continue
        if [[ "$(sha "$backup")" == "$VANILLA_EXE_SHA" ]]; then KPM_ORIGINAL=$backup; return 0; fi
    done
    KPM_PROBLEM="KotOR Patch Manager's copy of the untouched game is missing or is not the Steam build this KMRP supports; remove the patches in KPM, or use Steam's 'Verify integrity of game files', then install KMRP"
    return 1
}

kpm_remove() {   # puts the untouched game back from KPM's copy and deletes FTD's install
    local f backup
    if [[ "$KPM_ORIGINAL" != "$EXE" ]]; then
        cp -p "$KPM_ORIGINAL" "$EXE.kmrp-tmp"
        mv -f "$EXE.kmrp-tmp" "$EXE"
    fi
    [[ "$(sha "$EXE")" == "$VANILLA_EXE_SHA" ]] || die "the untouched game could not be put back from KotOR Patch Manager's copy"
    for f in $KPM_FILES; do rm -rf -- "${MACOS:?}/$f"; done
    for backup in ${(f)"$(kpm_backups)"}; do rm -f -- "$backup"; done
    # What KPM's own removal does with the options it recorded (PatchOptionsIni.RemoveSections):
    # KMRP's, the controller patch's and the widescreen patch's.
    local kmrp_ini=$OPTIONS_INI
    for OPTIONS_INI in "$kmrp_ini" "${kmrp_ini:h}/kmrp-controller.ini" "${kmrp_ini:h}/k1widescreenpatch.ini"; do
        options_remove
    done
    OPTIONS_INI=$kmrp_ini
}

# ---------------------------------------------------------------------- patch options
# The values the kmrp patch was installed with, where a KotOR Patch Manager with patch options
# records them (LaneDibello/Kotor-Patch-Manager#310, PatchOptionsIni) and kmrp.dylib reads them
# (patches/kmrp-layout/options.cpp): configs/kmrp.ini beside KOTOR_Exe, section [Patch Options],
# one key per option, a toggle as 1 or 0, CRLF line ends. Only that section is KMRP's installer's
# or KPM's; the rest of the file is the patch's own settings and is kept byte for byte. As
# Windows' installer (src/patcher/KpmEdition.cs, WritePatchOptions).
options_rest() {   # the file without the section, as KPM's WithoutSection leaves it
    [[ -f "$OPTIONS_INI" ]] || return 0
    perl -e '
        local $/; my $text = <STDIN>; my ($kept, $in, $dropped) = ("", 0, 0);
        for my $line (split /\n/, $text, -1) {
            (my $trimmed = $line) =~ s/^\s+|\s+$//g;
            if ($trimmed =~ /^\[(.*)\]$/) {
                (my $name = $1) =~ s/^\s+|\s+$//g;
                $in = lc($name) eq "patch options"; $dropped ||= $in;
            }
            $kept .= "$line\n" unless $in;
        }
        if (!$dropped) { print $text; exit }
        chop $kept if length $kept;
        $kept =~ s/^[\r\n]+//;
        print $kept;' < "$OPTIONS_INI"
}

options_write_one() {   # options_write_one <key=value lines, CRLF>: the section first, then whatever else $OPTIONS_INI held
    local made_dir=0 existed=0 rest
    [[ -d "${OPTIONS_INI:h}" ]] || { mkdir "${OPTIONS_INI:h}"; made_dir=1; }
    [[ -f "$OPTIONS_INI" ]] && existed=1
    rest=$(options_rest; print -n x); rest=${rest%x}
    {
        printf '[Patch Options]\r\n%s' "$1"
        [[ -n "$rest" ]] && printf '\r\n%s' "$rest"
    } > "$OPTIONS_INI.kmrp-tmp"
    mv -f "$OPTIONS_INI.kmrp-tmp" "$OPTIONS_INI"
    (( made_dir )) && record dir "${OPTIONS_INI:h}" "-" "-"
    record options "$OPTIONS_INI" "-" "$existed"
}

# Each patch's own file: configs/kmrp.ini, configs/kmrp-controller.ini while the controller
# patch is installed, and configs/k1widescreenpatch.ini for FTD's widescreen patch.
# The widescreen patch's GUI mode (gui-mode, since FTD's patch has the option) is "gui-files",
# the layouts from KMRP's .gui files. kmrp.dylib asks for that mode itself at start
# (K1Widescreen_UseGuiFileLayouts, kmrp-assets/widescreen.cpp) whatever the file says; the file
# is so that KotOR Patch Manager shows the mode KMRP runs in, and keeps it on its next Apply.
WIDESCREEN_OPTIONS=$'gui-mode=gui-files\r\n'
options_write() {
    local kmrp_ini=$OPTIONS_INI lines
    lines=$(printf 'map-notes=%d\r\nhd-icons=%d\r\nmarked-empty=%d\r\ndebug-logs=%d\r\n' $MAP_NOTES $HD_ICONS $MARKED_EMPTY $DEBUG_LOGS; print -n x)
    # keep-anti-aliasing is no option of the patch's manifest: a line only when asked for
    # (--keep-anti-aliasing), which the module reads (kmrp-assets/resolution.cpp).
    (( KEEP_AA )) && lines="${lines%x}"$'keep-anti-aliasing=1\r\n'x
    options_write_one "${lines%x}"
    if (( CONTROLLER )); then
        OPTIONS_INI="${kmrp_ini:h}/kmrp-controller.ini"
        lines=$(printf 'debug-logs=%d\r\n' $DEBUG_LOGS; print -n x)
        options_write_one "${lines%x}"
        OPTIONS_INI=$kmrp_ini
    fi
    OPTIONS_INI="${kmrp_ini:h}/k1widescreenpatch.ini"
    options_write_one "$WIDESCREEN_OPTIONS"
    OPTIONS_INI=$kmrp_ini
}

options_remove() {   # the section out; a file with nothing else, and then an empty folder, go too
    [[ -f "$OPTIONS_INI" ]] || return 0
    local rest
    rest=$(options_rest; print -n x); rest=${rest%x}
    if [[ -z "${rest//[[:space:]]/}" ]]; then
        rm -f "$OPTIONS_INI"
        rmdir "${OPTIONS_INI:h}" 2>/dev/null || true
    else
        print -rn -- "$rest" > "$OPTIONS_INI.kmrp-tmp"
        mv -f "$OPTIONS_INI.kmrp-tmp" "$OPTIONS_INI"
    fi
}

# ---------------------------------------------------------------------- manifest
# One line per file KMRP wrote: kind<TAB>absolute path<TAB>sha256 as written<TAB>backup name
#   added    -- did not exist before; uninstall deletes it if unchanged
#   replaced -- existed before; the original is in backup/, uninstall restores it if ours is unchanged
#   exe      -- KOTOR_Exe; backup/KOTOR_Exe is the original
#   dir      -- a directory KMRP created; removed if empty
#   ini      -- a swkotor.ini key (path column), the value written, the value before or "-";
#               uninstall puts the old value back if the key still holds KMRP's
#   options  -- configs/kmrp.ini, whose [Patch Options] section KMRP wrote; uninstall takes the
#               section out and keeps anything else in the file
#   settings -- kmrp-controller.ini, written because it was absent; the player's to edit, so
#               uninstall deletes it if unchanged and otherwise keeps it without complaint
#   moved    -- the player's old kmrp-controller.ini (sha column: where it was), moved to
#               KMRP/controller.ini, a copy in backup/; rollback puts it back, uninstall keeps it
record() { print -r -- "$1	$2	$3	$4" >> "$STATE/manifest.tsv"; }

set_ini() {   # set_ini <key> <value>: writes it and records what it replaced
    local before
    before=$(ini_value "$1")
    [[ "$before" == "$2" ]] && return 0
    ini_edit set "$1" "$2"
    record ini "$1" "$2" "${before:--}"
}

# The controller's settings (rumble), read by the controller code in kmrp.dylib while the game runs. As on
# Windows (KmrpPatcher.cs, DefaultSettings, whose values these are): written only when there
# is none, an existing copy is the player's and is never replaced, and uninstall removes it
# only if it is still exactly as written. Only the log's location differs.
# The Xbox-style HUD is the controller's standard on the Mac (the maintainer, 2026-10-07: "always
# add this to the ini file ... this is standard with controller"), so a settings file from before
# it, which has no [Hud] section, is given one; nothing else in the player's file is touched, and
# a file that has the section keeps what it says.
install_settings() {
    # The player's file of before 2026-10-20, beside swkotor.ini, moved to where the module reads
    # it now (as the module itself would move it). Copied aside and recorded first, so that a
    # failed install puts it back as it was, [Hud] line or not.
    if [[ -e "$OLD_SETTINGS" && ! -e "$SETTINGS" ]]; then
        BACKUP_SEQ=$(( BACKUP_SEQ + 1 ))
        local moved_name="$(printf %05d $BACKUP_SEQ)-${OLD_SETTINGS:t}"
        cp -p "$OLD_SETTINGS" "$STATE/backup/$moved_name"
        record moved "$SETTINGS" "$OLD_SETTINGS" "$moved_name"
        mkdir -p "${SETTINGS:h}"
        mv "$OLD_SETTINGS" "$SETTINGS"
        say "Moved your ${OLD_SETTINGS:t} to ${SETTINGS/#${INI:h}\//}, where KMRP reads it now."
    fi
    if [[ -e "$SETTINGS" ]]; then
        if grep -qi '^[[:space:]]*\[hud\]' "$SETTINGS"; then
            say "Kept your ${SETTINGS:t}."
        else
            [[ -z "$(tail -c 1 "$SETTINGS")" ]] || print >> "$SETTINGS"
            cat >> "$SETTINGS" <<'EOF'

[Hud]
; Xbox (laid out like the original Xbox version's while the pad is in use; the
; game's own with mouse and keyboard) or PC (the game's own HUD always).
; Read when the game starts. KotOR Patch Manager's "Xbox-style HUD" option, where
; the manager offers options, decides instead of this line.
Style=Xbox
EOF
            say "Kept your ${SETTINGS:t}, and added the Xbox-style HUD's setting to it ([Hud] Style=Xbox)."
        fi
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

[Hud]
; Xbox (laid out like the original Xbox version's while the pad is in use; the
; game's own with mouse and keyboard) or PC (the game's own HUD always).
; Read when the game starts. KotOR Patch Manager's "Xbox-style HUD" option, where
; the manager offers options, decides instead of this line.
Style=Xbox
EOF
    record settings "$SETTINGS" "$(sha "$SETTINGS")" "-"
}


install_file() {   # install_file <source> <destination directory>
    local src=$1 dir=$2 name=${1:t} target="$2/${1:t}" backup_name="-"
    # A name written twice would back up KMRP's own first copy as "the original", and
    # uninstall would restore it (the Windows installer hit this with i_checkbox01.tga). The
    # file system ignores case, so the check does too.
    if grep -qiF -- "	$target	" "$STATE/manifest.tsv"; then
        die "the package installs $name twice"
    fi
    # KMRP's art pack already there is KMRP's own: one an earlier install left beside KotOR
    # Patch Manager's module of KMRP, or a leftover once that module went. It is no original of the
    # player's to back up and put back (restore_from_manifest settles it at uninstall).
    if [[ -e "$target" && "$name" != "$KMRP_PACK" ]]; then
        BACKUP_SEQ=$(( BACKUP_SEQ + 1 ))
        backup_name="$(printf %05d $BACKUP_SEQ)-$name"
        cp -p "$target" "$STATE/backup/$backup_name"
    fi
    # Recorded before it is written, as the modules are (do_install), and written under another
    # name and renamed: a copy cut short (a full disk, with the 64 MB pack) leaves no part of a
    # file at the target, so rollback finds either the file as it was, put back from its backup,
    # or the whole of KMRP's, removed.
    record "$([[ "$backup_name" == "-" ]] && print added || print replaced)" "$target" "$(sha "$src")" "$backup_name"
    if ! cp "$src" "$target.kmrp-tmp"; then
        rm -f "$target.kmrp-tmp"
        die "could not write $target"
    fi
    mv -f "$target.kmrp-tmp" "$target"
}

# ---------------------------------------------------------------------- install
# Explicit plist path keeps stand-in installs confined to their temporary HOME.
fullscreen_value() { defaults read "$1" DisplayFullScreen 2>/dev/null || true; }
set_fullscreen() {
    local old=$(fullscreen_value "$ASPYR_PREFS")
    [[ "$old" == 1 ]] && return 0
    record fullscreen "$ASPYR_PREFS" 1 "${old:--}"
    mkdir -p "${ASPYR_PREFS:h}"
    defaults write "$ASPYR_PREFS" DisplayFullScreen -bool true
    [[ "$(fullscreen_value "$ASPYR_PREFS")" == 1 ]] || die "could not enable fullscreen"
}
restore_fullscreen() {
    local target=$1 recorded=$2 backup=$3
    [[ "$(fullscreen_value "$target")" == "$recorded" ]] || return 0
    if [[ "$backup" == - ]]; then
        defaults delete "$target" DisplayFullScreen >/dev/null
    else
        defaults write "$target" DisplayFullScreen -bool "$([[ "$backup" == 1 ]] && echo true || echo false)"
    fi
}

# ---------------------------------------------------------------------- the art made ahead
# What the module makes the first time the game starts at a size (patches/kmrp-assets/assets.cpp:
# the common files, store/, and the size's set, sets/<W>x<H>/, in ~/Library/Caches/KMRP/<build>),
# made here instead, for the size chosen and every size the display offers that KMRP covers, as
# Windows' installer makes them (src/patcher/ArtPreparation.cs; the maintainer, 2026-10-19:
# "smoother user experience comes priority"). bin/kmrp-prepare is the module's own code in a
# program (tools/kmrp-prepare.cpp); its helpers keep their state in globals, so one size a
# process, several side by side: half the processor's threads, at most six (Windows' rule).
# Measured 2026-11-03 on a 14" MacBook Pro (M5, ten threads, so five at once): the common files
# 3.1 s and a set 1.3 s alone; the 23 sizes its display offers and the common files 6.2 s, 23 s
# one at a time; 3.9 GB of cache. Over that cache the module's own Prepare for 1512x982, run
# without the game by Test-MacAssets.py's driver, took 0.6 s, against 5.1 s over an empty one
# (the fonts aside, which the game still makes; not yet timed in the game itself).
#
# Not fatal, and never undone by a failed install (it runs once the install is complete): a size
# that is not made here is made by the game when it first starts at it, and is said.
# KMRP_DISPLAY_SIZES (sizes, space-separated) stands in for the display's list in the
# installer's own test, which has to make the same on any Mac.
offered_sizes() {   # offered_sizes <prepare> <pack>
    if [[ -n "${KMRP_DISPLAY_SIZES+set}" ]]; then print -l ${=KMRP_DISPLAY_SIZES}; return 0; fi
    "$1" --sizes "$2" 2>/dev/null || true
}

PREPARE_STOP=0   # set by the INT/TERM trap while prepare_art runs

prepare_art() {   # prepare_art <the size chosen>
    local prepare="$BIN/kmrp-prepare" pack="$MACOS/patches/kmrp-assets.pack" assets="$GAME/Contents/Assets"
    PREPARED=0
    [[ -x "$prepare" && -f "$pack" ]] || return 0
    # An x86_64 program, as the game: without Rosetta neither runs yet.
    if ! "$prepare" --check >/dev/null 2>&1; then
        warn "KMRP's art was not made ahead (bin/kmrp-prepare does not run here: Rosetta, which the game needs as well, may not be installed yet); the game makes it when it first starts."
        return 0
    fi
    local -a sizes queue failed
    local -A running   # the program's own PID, for each item being made
    local s
    sizes=("$1")
    for s in ${(f)"$(offered_sizes "$prepare" "$pack")"}; do
        if [[ "$s" == <->x<-> ]] && (( ! ${sizes[(Ie)$s]} )); then sizes+=("$s"); fi
    done
    local total=${#sizes} threads workers
    threads=$(sysctl -n hw.logicalcpu 2>/dev/null || echo 2)
    [[ "$threads" == <-> ]] || threads=2
    workers=$(( threads / 2 ))
    if (( workers < 1 )); then workers=1; fi
    if (( workers > 6 )); then workers=6; fi
    local dir="$WORK/prepare" ready=0 st item pid store=0 stopped="" last=$SECONDS finished
    mkdir -p "$dir"
    # The install is complete by now, so Ctrl-C or a TERM stops only this step: the programs
    # running are stopped, and the install ends as it would have, saying what is left to the game.
    # (The script's own trap, `exit 1`, would have left them running and $WORK behind.)
    PREPARE_STOP=0
    trap 'PREPARE_STOP=1' INT TERM
    queue=(store $sizes)
    say "Unpacking KMRP's art..."
    while (( ${#queue} || ${#running} )); do
        while (( ! PREPARE_STOP && ${#queue} && ${#running} < workers )); do
            item=${queue[1]}; shift queue
            # The program itself in the background, so that $! is its PID.
            "$prepare" "$assets" "$pack" "$item" >"$dir/$item.log" 2>&1 &
            # Through a plain variable: zsh takes `running[$item]=$!` as the text "$!".
            pid=$!
            running[$item]=$pid
        done
        # A set takes seconds; ten minutes without one finished is a process that hangs.
        if (( PREPARE_STOP )); then stopped="was stopped"
        elif (( SECONDS - last > 600 )); then stopped="took too long to make and was stopped"; fi
        if [[ -n "$stopped" ]]; then
            for item pid in ${(kv)running}; do
                kill "$pid" 2>/dev/null || true
                wait "$pid" 2>/dev/null || true
                if [[ $item != store ]]; then failed+=("$item"); fi
            done
            for item in $queue; do
                if [[ $item != store ]]; then failed+=("$item"); fi
            done
            running=(); queue=()
            warn "KMRP's art $stopped; the install itself is complete."
            break
        fi
        # Each one finished, in whatever order: a child that has exited is gone to kill -0, and
        # zsh keeps its status for wait.
        finished=0
        for item pid in ${(kv)running}; do
            kill -0 "$pid" 2>/dev/null && continue
            st=0; wait "$pid" 2>/dev/null || st=$?
            unset "running[$item]"
            finished=1; last=$SECONDS
            if [[ $item == store ]]; then
                if (( st == 0 )); then store=1; fi
                continue
            fi
            if (( st == 0 )); then (( ++ready )); else failed+=("$item"); fi
            say "$ready of $total resolutions ready..."
        done
        (( finished )) || sleep 0.2
    done
    trap 'exit 1' INT TERM
    local why
    if (( ! store )); then
        why=$(grep -v '^made ' "$dir/store.log" 2>/dev/null | tail -1 || true)
        warn "KMRP's common art could not be made now${why:+ ($why)}; the game makes it when it first starts."
    fi
    for item in $failed; do
        why=$(grep -v -e '^made ' -e '^failed ' "$dir/$item.log" 2>/dev/null | tail -1 || true)
        warn "KMRP's art for $item could not be made now${why:+ ($why)}; the game makes it when it first starts at that size."
    done
    if (( store && ${#failed} == 0 )); then PREPARED=$total; fi
    return 0
}

do_install() {
    find_game; set_paths; refuse_if_running
    if (( APPSTORE )); then do_install_app_store; return 0; fi
    [[ -f "$PAYLOAD/SHA256SUMS" ]] || die "the package is incomplete (SHA256SUMS missing)"
    say "KMRP $KMRP_VERSION for macOS"
    say "Game: $GAME"

    say "Checking the package..."
    (cd "$PAYLOAD" && shasum -a 256 -s -c SHA256SUMS) || die "the package is damaged: a file does not match SHA256SUMS. Download it again."

    if [[ -d "$STATE" ]]; then
        die "KMRP is already installed (state in $STATE). Run uninstall first."
    fi
    local exe_sha kpm=0 for_kpm=0 check=0; exe_sha=$(sha "$EXE")
    if kpm_present; then
        kpm_check || check=$?
        case $check in
            0)  kpm=1
                say "FTD's widescreen patch is installed through KotOR Patch Manager: KMRP installs it again with its own patch on top (the version KMRP was built with)." ;;
            2)  for_kpm=1
                say "KotOR Patch Manager manages this game ($KPM_OTHERS): KMRP is installed for it. KOTOR_Exe and KPM's files are left as they are." ;;
            *)  die "$KPM_PROBLEM." ;;
        esac
    elif [[ "$exe_sha" == "$APPSTORE_EXE_SHA" ]]; then
        die "this is the Mac App Store's KOTOR_Exe in a folder that is not that game's. KMRP installs for the App Store's game where the App Store put it (kmrp-mac.sh install --app-store)."
    elif [[ "$exe_sha" != "$VANILLA_EXE_SHA" ]]; then
        die "KOTOR_Exe is not the unmodified Steam build this KMRP supports (SHA-256 $exe_sha, expected ${VANILLA_EXE_SHA[1,16]}...). If another patch is installed, remove it first; Steam's 'Verify integrity of game files' restores the original."
    fi
    [[ -f "$TEXTURE_PACK" ]] || die "the game's texture pack is missing: $TEXTURE_PACK"

    choose_resolution
    local size="${WIDTH}x${HEIGHT}" from derived=0
    if is_listed_size "$size"; then
        from=$size
    else
        from=$(nearest_size)
        [[ -n "$from" ]] || die "the package lists no menu sets (sizes.txt)"
        derived=1
    fi
    say "Resolution: $size$([[ $RESOLUTION == half ]] && echo ' (the resolution macOS is set to)')"
    if (( derived )); then
        say "Menus: KMRP's layout blended for $size (the build has no set for it); fonts and art from $from"
    else
        say "Menus: KMRP's $size set"
    fi
    say "Map note corrections: $([[ $MAP_NOTES == 1 ]] && echo on || echo off)"
    say "HD icons: $([[ $HD_ICONS == 1 ]] && echo on || echo off)"
    say "Marked empty containers: $([[ $MARKED_EMPTY == 1 ]] && echo on || echo off)"
    say "Controller support: $([[ $CONTROLLER == 1 ]] && echo on || echo off)"
    say "High FPS Fix: $([[ $HIGH_FPS == 1 ]] && echo on || echo off)"
    say "Debug logs: $([[ $DEBUG_LOGS == 1 ]] && echo on || echo off)"
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
    # The helpers run from a copy without the quarantine flag. A downloaded package keeps the
    # flag on every file (cp copies it too), and Gatekeeper kills a flagged helper as it
    # starts: exit 137, `spctl` "rejected" (tested 2026-09-30). Inside KMRP Installer.app the
    # package is read-only, so the flag cannot be taken off where it is.
    cp -R "$PAYLOAD/bin" "$WORK/bin"
    xattr -dr com.apple.quarantine "$WORK/bin" 2>/dev/null || true
    BIN="$WORK/bin"

    if (( derived )); then
        # The module blends the set when the game starts; whether it can is known now.
        "$BIN/kmrp-guiblend" "$PAYLOAD/gui-blend.bin" "$WIDTH" "$HEIGHT" >/dev/null ||
            die "KMRP has no menus for $size: it is outside the shapes its sets cover (4:3 to 32:9)"
    fi

    if (( kpm )); then
        say "Removing FTD's KotOR Patch Manager install..."
        kpm_remove
    fi

    # KMRP's one patch (FTD's widescreen patch and Stray Bug Fixes with KMRP's code), one build
    # since 2026-10-04: controller support, map notes and debug logs are its options. This
    # installer resolves them as a KotOR Patch Manager with patch options does: the hook list
    # without the controller's hooks when that option is off, and the chosen values in
    # configs/kmrp.ini, which the module reads. (Until then: four builds, one per choice.)
    if (( for_kpm )); then
        # As Windows' install for KPM: KPM's runtime, its patch list and KOTOR_Exe stay KPM's.
        # Nothing beside the game since 2026-10-04: SDL is inside the module. The options are
        # chosen in KPM now, where controller support is on unless a KPM with patch options
        # turns it off, and this installer's own choice does not reach KPM's Apply. So no
        # options are recorded here either.
        if (( ! CONTROLLER || ! MAP_NOTES || ! HD_ICONS || ! MARKED_EMPTY || DEBUG_LOGS )); then
            warn "KotOR Patch Manager installs KMRP here, so KMRP's options are chosen in KPM (with patch options; KPM 0.7.1 installs controller support and map notes, without logs). The choices made in this installer are not applied."
        fi
    else
        say "Backing up KOTOR_Exe..."
        cp -p "$EXE" "$STATE/backup/KOTOR_Exe"
        [[ "$(sha "$STATE/backup/KOTOR_Exe")" == "$VANILLA_EXE_SHA" ]] || die "the backup copy does not match"

        say "Installing the engine patches..."
        install_file "$PAYLOAD/engine/KotorPatcher.dylib" "$MACOS"
        # A folder holding only an earlier KMRP's art pack is KMRP's leftover (lone_pack).
        if lone_pack; then rm -f "$MACOS/patches/$KMRP_PACK"; rmdir "$MACOS/patches"; fi
        mkdir "$MACOS/patches"; record dir "$MACOS/patches" "-" "-"
        # Each patch's module, out of the patch as KPM takes it (binaries/macos_x86_64.dylib) and
        # under the name KPM gives it, the patch's id: the package does not carry them a second
        # time. KMRP's holds SDL, the menu sets and the artwork.
        local n module
        for n in {1..${#KPATCH_FILES}}; do
            module="$MACOS/patches/${KPATCH_IDS[n]}.dylib"
            unzip -p "$PAYLOAD/engine/${KPATCH_FILES[n]}" binaries/macos_x86_64.dylib > "$module" || true
            # Recorded before it is checked, so that an install that stops here takes it out again.
            record added "$module" "$(sha "$module")" "-"
            [[ -s "$module" ]] || die "${KPATCH_FILES[n]} holds no module"
            # KMRP's own module is signed ad hoc by its build. FTD's are as KPM's
            # create-patch.py leaves them, unsigned, which an x86_64 library may be.
            if [[ "${KPATCH_IDS[n]}" == (kmrp*|high-fps-fixes) ]]; then
                codesign --verify "$module" || die "the module taken out of ${KPATCH_FILES[n]} is damaged"
            fi
        done
        # One hook list per choice of the two optional patches, each staged by KPM's own code.
        local hook_list=patch_config
        (( CONTROLLER )) || hook_list+=.controller-off
        (( HIGH_FPS )) && hook_list+=.high-fps
        hook_list+=.toml
        cp "$PAYLOAD/engine/$hook_list" "$MACOS/patch_config.toml"
        record added "$MACOS/patch_config.toml" "$(sha "$MACOS/patch_config.toml")" "-"
        options_write
        # KPM's own records of this install, so KPM recognises it and can take it over: the
        # untouched game in KPM's format first (KPM's Apply starts from it), then its state.
        write_kpm_backup
        write_kpm_state
        "$BIN/kmrp-macho" add-dylib "$EXE" "$LOADER" >/dev/null
        codesign --force --sign - --identifier KOTOR_Exe "$EXE" 2>/dev/null
        codesign --verify "$EXE"
        "$BIN/kmrp-macho" has-dylib "$EXE" KotorPatcher.dylib
        record exe "$EXE" "$(sha "$EXE")" "KOTOR_Exe"
    fi
    deliver_kpatch $for_kpm
    # KMRP's art, beside the module however the module got there: KPM's Apply replaces modules and
    # leaves the rest of the folder, as on Windows (tools/kmrp_pack.py).
    mkdir -p "$MACOS/patches"
    install_file "$PAYLOAD/engine/kmrp-assets.pack" "$MACOS/patches"

    say "Setting the resolution in swkotor.ini..."
    # UseGuiFileLayouts is not written any more (2026-10-04): the module answers for it itself
    # whenever it has menus for the size (patches/kmrp-assets/layouts_ini.cpp).
    # The size the game starts at. Since 2026-10-04 the resolution is chosen in the game
    # (Options, Graphics, Screen Resolution lists every size this display offers, and KMRP
    # follows a change at once), so a size of this display is written as the game's own Width
    # and Height, which the game rewrites when the player chooses another. Only a size the
    # display does not offer (--size, for a window or another display) is still forced with
    # ForceWidth and ForceHeight, which the game's own list cannot change.
    local geo=(${=$(display_geometry)}) offered=0
    if (( ${#geo} >= 4 )) && { [[ "$size" == "${geo[1]}x${geo[2]}" ]] || [[ "$size" == "${geo[3]}x${geo[4]}" ]]; }; then offered=1; fi
    if (( offered )); then
        set_ini Width "$WIDTH"
        set_ini Height "$HEIGHT"
    else
        set_ini ForceWidth "$WIDTH"
        set_ini ForceHeight "$HEIGHT"
    fi
    # Anti-aliasing off on a display of 3840x2160 pixels or more (2026-10-09, at the maintainer's
    # word). Measured on a 4K television at 60 Hz, the main menu, whose layers of smoke make it
    # the game's heaviest scene: 59 frames a second at 2x, a frame in twenty over the 16.7 ms a
    # refresh allows, which V-Sync shows as a stutter; 82 with it off. Frame-buffer effects and
    # soft shadows made no difference (60 and 61). Recorded like the size: uninstall puts back
    # what was there, unless the player has chosen another setting in the game since.
    if (( ! KEEP_AA )) && (( ${#geo} >= 4 )) && (( geo[3] * geo[4] >= 3840 * 2160 )); then
        local aa; aa=$(ini_value "Anti Aliasing")
        if [[ -n "$aa" && "$aa" != 0 ]]; then
            say "Turning anti-aliasing off for this ${geo[3]}x${geo[4]} display (it was ${aa}x)..."
            set_ini "Anti Aliasing" 0
        fi
    fi
    # Nothing is written for the game's Screen Resolution list: it is what the connected display
    # reports, as on Windows since 2026-10-07. (For one day a checklist in KMRP Installer wrote
    # its choice beside KOTOR_Exe as kmrp-resolutions.txt; the list of such an install is removed
    # with it, being a file that install recorded, and one left over is removed here.)
    rm -f "$MACOS/kmrp-resolutions.txt"
    say "Making fullscreen the default in Aspyr’s launcher..."
    set_fullscreen
    if (( CONTROLLER )); then install_settings; fi

    xattr -dr com.apple.quarantine "$MACOS" 2>/dev/null || true

    {
        print -r -- "version=$KMRP_VERSION"
        print -r -- "game=$GAME"
        print -r -- "installed=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        print -r -- "exe_before=$VANILLA_EXE_SHA"
        print -r -- "exe_after=$(sha "$EXE")"
        print -r -- "resolution=$size"
        print -r -- "resolution_choice=$RESOLUTION"
        print -r -- "menu_set=$([[ $derived == 1 ]] && echo "blended, fonts and art from $from" || echo "$from")"
        print -r -- "map_notes=$MAP_NOTES"
        print -r -- "hd_icons=$HD_ICONS"
        print -r -- "marked_empty=$MARKED_EMPTY"
        print -r -- "controller=$CONTROLLER"
        print -r -- "high_fps=$HIGH_FPS"
        print -r -- "debug_logs=$DEBUG_LOGS"
        print -r -- "for_kpm=$for_kpm"
        print -r -- "kpatch=${KPATCH_FOLDER:--}"
        print -r -- "complete=1"
    } > "$STATE/install.info"
    INSTALLING=0
    # The install is complete: from here nothing is undone, and a failure only leaves a size to
    # the game (called in a list, so that no command of it can stop the script).
    PREPARED=0
    if (( PREPARE )); then prepare_art "$size" || true; fi
    rm -rf "$WORK"
    if (( for_kpm )); then
        say "Installed for KotOR Patch Manager: the resolution, the controller's settings and KMRP's art pack. KOTOR_Exe was not modified, and nothing was written to the game's override folder: the menus are in KMRP's art pack, beside where KotOR Patch Manager puts KMRP's module."
        if [[ -n "$KPATCH_FOLDER" ]]; then
            say "KMRP's patch is in $KPATCH_FOLDER, with FTD's Widescreen Patch and Stray Bug Fixes, which it requires"$( (( CONTROLLER )) && print -n ', and the controller patch' )". Open KotOR Patch Manager, tick them, and press Apply."
        fi
    else
        if (( PREPARED )); then
            say "Installed: KMRP's patch, on FTD's Widescreen Patch and Stray Bug Fixes, with the menus for every resolution in its art pack, made for the $PREPARED resolutions of this display in ~/Library/Caches/KMRP. Nothing was written to the game's override folder."
        else
            say "Installed: KMRP's patch, on FTD's Widescreen Patch and Stray Bug Fixes, with the menus for every resolution in its art pack. Nothing was written to the game's override folder. The first start of the game at a resolution not made yet unpacks what it needs, which takes a few seconds."
        fi
        say "KOTOR_Exe was modified (one load command, re-signed ad hoc); the original is in $STATE/backup."
        [[ -n "$KPATCH_FOLDER" ]] && say "KMRP's patch is also in KotOR Patch Manager's patch folder ($KPATCH_FOLDER)."
    fi
    say "To undo everything: Uninstall in KMRP Installer, or kmrp-mac.sh uninstall."
}

# ---------------------------------------------------------------------- uninstall
rollback() {
    local kept=0
    ROLLING_BACK=1
    restore_from_manifest 1 || kept=$?
    ROLLING_BACK=0
    if (( kept )); then
        # A file KMRP replaced that is not as KMRP wrote it: its original stays in backup/, and
        # the state stays with it (install.info says complete=0), for uninstall to finish.
        warn "$kept file(s) could not be put back; their originals are kept in $STATE/backup. Run uninstall to finish."
    else
        rm -rf "$STATE"; rmdir "$STATE_ROOT" 2>/dev/null || true
    fi
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

handed_over() {   # 0 once KPM's Apply has rewritten any of the runtime KMRP's install put in
    # Not patch_config.toml alone, as Windows can: on the Mac KPM's Apply writes it byte for
    # byte as KMRP did (the same KPatchCore, the same patch), and re-extracts kmrp.dylib the
    # same, while KOTOR_Exe (re-signed), KotorPatcher.dylib (KPM's own) and
    # kpm_install_state.json change (seen with KPM 0.7.1, 2026-10-01). A KOTOR_Exe back to the
    # untouched game is not a takeover but KPM removing everything; a file gone is not either.
    local kind target recorded backup
    while IFS=$'\t' read -r kind target recorded backup; do
        [[ "$kind" == (added|exe) ]] && is_runtime_path "$target" && [[ -f "$target" ]] || continue
        local now=$(sha "$target")
        [[ "$now" == "$recorded" ]] && continue
        [[ "$kind" == exe && "$now" == "$VANILLA_EXE_SHA" ]] && continue
        return 0
    done < "$STATE/manifest.tsv"
    return 1
}

restore_from_manifest() {   # restore_from_manifest <quiet>
    local quiet=${1:-0} kept=0 kind target recorded backup now over=0 patches_ours=0
    local pack="$MACOS/patches/$KMRP_PACK"
    [[ -f "$STATE/manifest.tsv" ]] || return 0
    # KotOR Patch Manager has taken over the runtime this install put in (its Apply rewrote
    # the runtime; handed_over): the runtime, the load command and KPM's records are KPM's now, and
    # removing any of them would break its install. Only KMRP's own content goes, as on
    # Windows (KpmEdition.cs, Restore).
    # When KMRP is the only patch KPM has, unticking it in KPM and pressing Apply would remove
    # KPM's whole runtime (PatchRemover.RemoveAllPatches), so that is done here instead and the
    # player has nothing left to do in KPM. With other patches in KPM's list, KMRP's module
    # cannot be taken out without KPM re-applying the rest; that is left to the player.
    local whole=0
    if handed_over; then
        over=1
        if kpm_holds_only_kmrp; then
            whole=1
        else
            (( quiet )) || say "KotOR Patch Manager has taken over the runtime KMRP installed (its Apply rewrote it), with other patches as well, so it is left in place for them. Untick KMRP in KPM and press Apply to finish."
        fi
    fi
    # Newest first, so directories are removed after the files in them.
    while IFS=$'\t' read -r kind target recorded backup; do
        # The art pack is settled after the rest (below): whether it stays depends on whether
        # KMRP's module is left, which this loop has not decided yet.
        if [[ "$target" == "$pack" ]]; then continue; fi
        if [[ "$kind" == dir && "$target" == "$MACOS/patches" ]]; then patches_ours=1; fi
        if (( over )) && is_runtime_path "$target"; then continue; fi
        case "$kind" in
            kpatch)
                # "created": KMRP put it there, removed while it is as written. "replaced": an
                # older KMRP's, brought up to date and left.
                # "swapped": FTD's Widescreen Patch from before the entry points KMRP needs, which
                # is put back while KMRP's copy is as written.
                if [[ "$backup" == created && -f "$target" ]]; then
                    if [[ "$(sha "$target")" == "$recorded" ]]; then rm -f "$target"
                    else (( quiet )) || warn "changed since install, left in place: $target"; fi
                elif [[ "$backup" == swapped && -f "$target" && -f "$STATE/backup/${target:t}" ]]; then
                    if [[ "$(sha "$target")" == "$recorded" ]]; then cp -pf "$STATE/backup/${target:t}" "$target"
                    else (( quiet )) || warn "changed since install, left in place: $target"; fi
                fi ;;
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
                    rmdir "${target:h}" 2>/dev/null || true   # the KMRP folder, when nothing else is in it
                elif [[ -e "$target" ]]; then
                    (( quiet )) || say "Kept your edited ${target:t}."
                fi ;;
            moved)
                # The player's kmrp-controller.ini, moved into the KMRP folder (install_settings).
                # A failed install puts it back as it was; uninstall leaves it where the module
                # reads it, being the player's.
                if (( ROLLING_BACK )) && [[ -f "$STATE/backup/$backup" && ! -e "$recorded" ]]; then
                    cp -p "$STATE/backup/$backup" "$recorded"
                    rm -f "$target"
                    rmdir "${target:h}" 2>/dev/null || true
                elif (( ! quiet )) && [[ -e "$target" ]]; then
                    say "Kept your ${target:t} (moved there from ${recorded:t} at install)."
                fi ;;
            replaced)
                if [[ -f "$target" && "$(sha "$target")" == "$recorded" ]]; then
                    cp -p "$STATE/backup/$backup" "$target"
                elif [[ -f "$target" && -f "$STATE/backup/$backup" && "$(sha "$target")" == "$(sha "$STATE/backup/$backup")" ]]; then
                    :   # never replaced: an install stopped between the record and the copy
                else
                    (( quiet )) || warn "changed since install, left in place (original kept in backup/$backup): $target"
                    kept=$(( kept + 1 ))
                fi ;;
            dir)
                rmdir "$target" 2>/dev/null || true ;;
            options)
                OPTIONS_INI=$target; options_remove ;;
            fullscreen)
                restore_fullscreen "$target" "$recorded" "$backup" ;;
            ini)
                now=$(ini_value "$target")
                if [[ "$now" == "$recorded" ]]; then
                    if [[ "$backup" == "-" ]]; then ini_edit delete "$target"; else ini_edit set "$target" "$backup"; fi
                elif [[ -n "$now" && "$target" == (Width|Height) ]]; then
                    :   # the game's own keys: the player chose another resolution in the game, which stays
                elif [[ -n "$now" ]]; then
                    (( quiet )) || warn "swkotor.ini: $target is $now now, not what KMRP set; left as it is (it was ${backup/#-/unset} before)"
                fi ;;
        esac
    done < <(tail -r "$STATE/manifest.tsv")
    if (( whole )); then
        (( quiet )) || say "KotOR Patch Manager had taken over KMRP's install, with no other patch; removing it as KPM would, and putting back the untouched game..."
        KPM_ORIGINAL="$STATE/backup/KOTOR_Exe"
        kpm_remove
    fi
    # KMRP's art pack: kept while KMRP's module stays (an install for KPM, or one KPM took over
    # beside other patches), which reads it and makes nothing without it; else removed, whatever
    # build's it is, being KMRP's.
    if [[ -f "$pack" ]]; then
        if kmrp_module_remains; then
            (( quiet )) || say "Kept KMRP's art pack, ${pack:t}: KotOR Patch Manager still installs KMRP's patch, whose module reads it. Untick KMRP in KPM and press Apply; KMRP's next install or the next uninstall in KPM's place removes it then."
        else
            rm -f "$pack"
            if (( patches_ours )); then rmdir "$MACOS/patches" 2>/dev/null || true; fi
        fi
    fi
    return $kept
}

kpm_holds_only_kmrp() {   # config, InstalledPatches (including module-less patches), and modules
    # "Only KMRP" is KMRP with the two patches it requires and installs, with or without its
    # controller patch, and nothing else.
    local id module installed patch_state="$MACOS/kpm_install_state.json"
    local count=0
    [[ -f "$MACOS/patch_config.toml" ]] || return 1
    for id in ${(f)"$(sed -n 's/^id = "\(.*\)"$/\1/p' "$MACOS/patch_config.toml")"}; do
        (( ${KMRP_IDS[(Ie)$id]} )) || return 1
        [[ "$id" == kmrp ]] && (( ++count ))
    done
    (( count > 0 )) || return 1
    if [[ -e "$patch_state" || -L "$patch_state" ]]; then
        # plutil parses JSON; missing/malformed/non-array state must retain the runtime.
        installed=$(plutil -extract InstalledPatches json -o - "$patch_state" 2>/dev/null) || return 1
        [[ "$installed" == \[*\] ]] || return 1
        # Only the space around an id and its quotes go: an id with a space inside it is not
        # one of KMRP's (until 2026-10-12 every space was removed, and "k mrp" passed for kmrp).
        setopt localoptions extendedglob
        for id in ${(s:,:)${${installed#\[}%\]}}; do
            id=${id##[[:space:]]##}; id=${id%%[[:space:]]##}
            id=${${id#\"}%\"}
            [[ -z "$id" ]] && continue
            (( ${KMRP_IDS[(Ie)$id]} )) || return 1
        done
    fi
    for module in "$MACOS"/patches/*(N); do
        [[ "$module" == *.pack ]] && continue   # KMRP's art, no module
        (( ${KMRP_IDS[(Ie)${module:t:r}]} )) || return 1
    done
    return 0
}

do_uninstall() {
    if (( APPSTORE )) || { [[ -n "$GAME" ]] && is_app_store_game "$GAME"; } ||
       [[ ! -f "$STATE/install.info" && -f "$APPSTORE_STATE/install.info" ]]; then
        [[ -n "$GAME" ]] || GAME=$(sed -n 's/^game=//p' "$APPSTORE_STATE/install.info" 2>/dev/null || true)
        [[ -n "$GAME" ]] || GAME=$(app_store_game) || die "KOTOR from the Mac App Store was not found in Applications."
        APPSTORE=1; set_paths
        do_uninstall_app_store
        return 0
    fi
    [[ -f "$STATE/install.info" ]] || die "KMRP is not installed (no $STATE/install.info)."
    [[ -n "$GAME" ]] || GAME=$(sed -n 's/^game=//p' "$STATE/install.info")
    set_paths; refuse_if_running
    say "Removing KMRP from $GAME"
    confirm "Uninstall KMRP?" || die "cancelled"
    local kept=0
    restore_from_manifest 0 || kept=$?
    # What the module and the install made in the cache, as Windows' Restore Original removes
    # its own (%LOCALAPPDATA%\KMRP\cache): made again if KMRP is installed again.
    local cache
    for cache in "$HOME/Library/Caches/KMRP" "$HOME/Library/Caches/KMRP-Controller"; do
        if [[ -d "$cache" ]]; then
            rm -rf "$cache"
            say "Removed KMRP's cache, ${cache/#$HOME/~}."
        fi
    done
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
    if (( APPSTORE )) || { [[ -n "$GAME" ]] && is_app_store_game "$GAME"; }; then
        APPSTORE=1; find_game; set_paths
        do_status_app_store
        return 0
    fi
    if [[ -f "$STATE/install.info" ]]; then
        [[ -n "$GAME" ]] || GAME=$(sed -n 's/^game=//p' "$STATE/install.info")
        set_paths
        cat "$STATE/install.info"
        (( BRIEF )) && return 0
        local total=0 changed=0 kind target recorded backup
        while IFS=$'\t' read -r kind target recorded backup; do
            case "$kind" in
                dir) continue ;;
                options)
                    if [[ -f "$target" ]]; then say "patch options (${target:t}): $(tr -d '\r' < "$target" | awk '/^\[/ { on = tolower($0) == "[patch options]"; next } on && /=/ { printf "%s ", $0 }')"
                    else say "patch options: none recorded (the defaults apply)"; fi
                    continue ;;
                fullscreen) say "Aspyr fullscreen=$(fullscreen_value "$target") (KMRP set $recorded)"; continue ;;
                moved) say "${target:t}: yours, moved there from ${recorded:t}"; continue ;;
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
        if (( APPSTORE )); then do_status_app_store; return 0; fi
        say "KMRP is not installed."
        say "game: $GAME"
        if kpm_present; then
            local check=0
            kpm_check || check=$?
            case $check in
                0) say "KOTOR_Exe: FTD's widescreen patch through KotOR Patch Manager (supported: KMRP replaces it)" ;;
                2) say "KOTOR_Exe: managed by KotOR Patch Manager ($KPM_OTHERS; supported: KMRP installs for KPM)" ;;
                *) say "KOTOR_Exe: a KotOR Patch Manager install KMRP cannot replace ($KPM_PROBLEM)" ;;
            esac
        elif [[ "$(sha "$EXE")" == "$VANILLA_EXE_SHA" ]]; then say "KOTOR_Exe: unmodified Steam build (supported)"
        elif [[ "$(sha "$EXE")" == "$APPSTORE_EXE_SHA" ]]; then
            say "KOTOR_Exe: the Mac App Store's, in a folder that is not that game's (not supported)"
        else say "KOTOR_Exe: modified or a different build"; fi
        (( BRIEF )) && return 0
        local geo=(${=$(display_geometry)})
        say "display: ${geo[1]}x${geo[2]} points, ${geo[3]}x${geo[4]} pixels"
        local candidate
        for candidate in "${geo[3]}x${geo[4]}" "${geo[1]}x${geo[2]}"; do
            if is_listed_size "$candidate"; then say "menu set for $candidate: in the package"
            else say "menu set for $candidate: blended at install (the package has no set for it)"; fi
        done
    fi
}

# ---------------------------------------------------------------------- the Mac App Store's game
# Nothing is written into the App Store's game (docs/macos-app-store.md): macOS does not start it
# once its bundle has changed. KMRP is an app of its own beside it, "KOTOR with KMRP", which
# holds the patcher, the hook list and the modules for that build (the package's appstore/,
# translated from Steam's by the build) and starts the game with them brought in
# (appstore/launcher.c, loader.c). The game started by its own icon is the game without KMRP.
#
# The sandboxed game reads /Applications and its own container and nothing else of the player's
# (measured 2026-10-12), so the app has to be in the folder the game is in. The game's settings
# are in its container, which this installer cannot write: nothing is set there. The module
# starts the game at the display's size, makes its menu sets in the container's caches, and the
# controller uses its default settings.
APPSTORE_STATE="$STATE_ROOT/macos-appstore"
APPSTORE_LAUNCHER_ID="io.github.rayesdiyab.kmrp.appstore-launcher"
APPSTORE_LAUNCHER_NAME="KOTOR with KMRP"

appstore_launcher_is_ours() {
    [[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$1/Contents/Info.plist" 2>/dev/null)" == "$APPSTORE_LAUNCHER_ID" ]]
}

# apply_delta <base> <delta> <out>: the file tools/appstore/make_delta.py described, made from
# its base. Both ends are held against the hashes the delta names.
apply_delta() {
    local want_base want_new
    want_base=$(sed -n 's/^base //p;/^data$/q' "$2" | head -1)
    want_new=$(sed -n 's/^new //p;/^data$/q' "$2" | head -1)
    [[ "$(sha "$1")" == "$want_base" ]] || return 1
    perl -e '
        use strict;
        my ($base, $delta, $out) = @ARGV;
        open my $d, "<:raw", $delta or die "$delta: $!\n";
        my $line = <$d>; chomp $line;
        $line eq "KMRP-DELTA 1" or die "not a delta\n";
        my ($size, @runs);
        while (defined($line = <$d>)) {
            chomp $line;
            last if $line eq "data";
            if ($line =~ /^size (\d+)$/) { $size = $1 }
            elsif ($line =~ /^(\d+) (\d+)$/) { push @runs, [$1, $2] }
        }
        open my $b, "<:raw", $base or die "$base: $!\n";
        my $data = do { local $/; <$b> };
        close $b;
        defined $size && length($data) == $size or die "the base has another length\n";
        for my $run (@runs) {
            my $got = read($d, my $bytes, $run->[1]);
            defined $got && $got == $run->[1] or die "the delta is short\n";
            substr($data, $run->[0], $run->[1]) = $bytes;
        }
        open my $o, ">:raw", $out or die "$out: $!\n";
        print $o $data;
        close $o or die "$out: $!\n";' "$1" "$2" "$3" || return 1
    [[ "$(sha "$3")" == "$want_new" ]]
}

do_install_app_store() {
    local payload="$PAYLOAD/appstore" folder="${GAME:h}"
    local app="$folder/$APPSTORE_LAUNCHER_NAME.app"
    [[ -f "$payload/loader.dylib" ]] || die "this package was built without the Mac App Store's game: it supports the Steam version only."
    say "KMRP $KMRP_VERSION for macOS"
    say "Game: $GAME (Mac App Store)"
    say "Checking the package..."
    (cd "$PAYLOAD" && shasum -a 256 -s -c SHA256SUMS) || die "the package is damaged: a file does not match SHA256SUMS. Download it again."
    local exe_sha; exe_sha=$(sha "$EXE")
    [[ "$exe_sha" == "$APPSTORE_EXE_SHA" ]] ||
        die "this is not the Mac App Store version this KMRP was made for (1.4.1; KOTOR_Exe is ${exe_sha[1,16]}..., expected ${APPSTORE_EXE_SHA[1,16]}...). After an update of the game, KMRP needs an update too."
    [[ -d "$APPSTORE_STATE" ]] && die "KMRP is already installed for the Mac App Store's game (state in $APPSTORE_STATE). Run uninstall --app-store first."
    if [[ -e "$app" ]] && ! appstore_launcher_is_ours "$app"; then
        die "$app exists and is not KMRP's. Move it away first."
    fi
    [[ -w "$folder" ]] || die "$folder cannot be written by this account. KMRP's app has to be beside the game there (the game reads nothing else of yours): install from an administrator's account."
    [[ -n "$SIZE" || "$RESOLUTION" == native ]] && warn "the resolution is not set for the Mac App Store's game (its settings are closed to this installer): it starts at the display's size, and Options, Graphics changes it."

    say "Map note corrections: $([[ $MAP_NOTES == 1 ]] && echo on || echo off)"
    say "HD icons: $([[ $HD_ICONS == 1 ]] && echo on || echo off)"
    say "Marked empty containers: $([[ $MARKED_EMPTY == 1 ]] && echo on || echo off)"
    say "Controller support: $([[ $CONTROLLER == 1 ]] && echo on || echo off)"
    say "High FPS Fix: $([[ $HIGH_FPS == 1 ]] && echo on || echo off)"
    say "Debug logs: $([[ $DEBUG_LOGS == 1 ]] && echo on || echo off)"
    confirm "Install KMRP for this game? The game itself is not changed: KMRP is added as the app \"$APPSTORE_LAUNCHER_NAME\" beside it." || die "cancelled"

    WORK=$(mktemp -d "${TMPDIR:-/tmp}/kmrp-install.XXXXXX")
    local staging="$WORK/$APPSTORE_LAUNCHER_NAME.app"
    local kmrp="$staging/Contents/Resources/kmrp"
    mkdir -p "$staging/Contents/MacOS" "$kmrp/patches" "$kmrp/configs"
    say "Making KMRP's modules for the Mac App Store's game..."
    local n id base
    for n in {1..${#KPATCH_FILES}}; do
        id=${KPATCH_IDS[n]}
        if [[ -f "$payload/$id.dylib" ]]; then
            cp "$payload/$id.dylib" "$kmrp/patches/$id.dylib"
            continue
        fi
        base="$WORK/$id.steam.dylib"
        unzip -p "$PAYLOAD/engine/${KPATCH_FILES[n]}" binaries/macos_x86_64.dylib > "$base" || true
        [[ -s "$base" ]] || { rm -rf "$WORK"; die "${KPATCH_FILES[n]} holds no module"; }
        apply_delta "$base" "$payload/$id.dylib.delta" "$kmrp/patches/$id.dylib" ||
            { rm -rf "$WORK"; die "the module $id for the Mac App Store's game could not be made from the package"; }
        rm -f "$base"
    done
    local hook_list=patch_config
    (( CONTROLLER )) || hook_list+=.controller-off
    (( HIGH_FPS )) && hook_list+=.high-fps
    cp "$payload/$hook_list.toml" "$kmrp/patch_config.toml"
    cp "$PAYLOAD/engine/KotorPatcher.dylib" "$payload/loader.dylib" "$kmrp/"
    cp "$PAYLOAD/engine/kmrp-assets.pack" "$kmrp/patches/"
    print -r -- "$GAME" > "$kmrp/game-path.txt"
    # The patch options, as kmrp.dylib and the controller's module read them (options_write).
    printf '[Patch Options]\r\nmap-notes=%d\r\nhd-icons=%d\r\nmarked-empty=%d\r\ndebug-logs=%d\r\n' $MAP_NOTES $HD_ICONS $MARKED_EMPTY $DEBUG_LOGS > "$kmrp/configs/kmrp.ini"
    (( KEEP_AA )) && printf 'keep-anti-aliasing=1\r\n' >> "$kmrp/configs/kmrp.ini"
    printf '[Patch Options]\r\n%s' "$WIDESCREEN_OPTIONS" > "$kmrp/configs/k1widescreenpatch.ini"
    if (( CONTROLLER )); then
        printf '[Patch Options]\r\ndebug-logs=%d\r\n' $DEBUG_LOGS > "$kmrp/configs/kmrp-controller.ini"
        # SDL beside the controller's module: the sandboxed game does not load the copy that
        # module unpacks to the game's container.
        cp "$payload/kmrp-sdl3.dylib" "$kmrp/patches/kmrp-sdl3.dylib"
    fi
    cp "$payload/kmrp-appstore-launcher" "$staging/Contents/MacOS/$APPSTORE_LAUNCHER_NAME"
    chmod 755 "$staging/Contents/MacOS/$APPSTORE_LAUNCHER_NAME"
    cp "$payload/Info.plist" "$staging/Contents/Info.plist"
    # The game's own icon, from the player's copy; KMRP's when it has none to give.
    local icon
    icon=$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIconFile' "$GAME/Contents/Info.plist" 2>/dev/null || true)
    icon="$GAME/Contents/Resources/${icon%.icns}.icns"
    [[ -f "$icon" ]] || icon="${PAYLOAD:h}/AppIcon.icns"
    [[ -f "$icon" ]] && cp "$icon" "$staging/Contents/Resources/AppIcon.icns"
    # A downloaded package's files carry the quarantine flag, with which the app would not start.
    xattr -cr "$staging" 2>/dev/null || true
    codesign --force --sign - "$staging" 2>/dev/null
    codesign --verify --strict "$staging" || { rm -rf "$WORK"; die "KMRP's app could not be signed"; }

    say "Adding \"$APPSTORE_LAUNCHER_NAME\" to ${folder}..."
    [[ -e "$app" ]] && rm -rf "$app"
    mv "$staging" "$app" || { rm -rf "$WORK"; die "could not write $app"; }
    rm -rf "$WORK"; WORK=""
    mkdir -p "$APPSTORE_STATE"
    {
        print -r -- "game=$GAME"
        print -r -- "store=mac-app-store"
        print -r -- "app=$app"
        print -r -- "version=$KMRP_VERSION"
        print -r -- "map_notes=$MAP_NOTES"
        print -r -- "hd_icons=$HD_ICONS"
        print -r -- "marked_empty=$MARKED_EMPTY"
        print -r -- "controller=$CONTROLLER"
        print -r -- "high_fps=$HIGH_FPS"
        print -r -- "debug_logs=$DEBUG_LOGS"
        print -r -- "complete=1"
    } > "$APPSTORE_STATE/install.info"
    say "Installed. Start the game with \"$APPSTORE_LAUNCHER_NAME\" in Applications (or Launchpad): that is the game with KMRP. \"Knights of the Old Republic\" itself is unchanged and starts without KMRP."
    say "The first start unpacks the menus for the display's size, which takes a few seconds. The game's log of a run: ~/Library/Logs/KMRP/appstore-game.log."
    say "To undo: Uninstall in KMRP Installer, or kmrp-mac.sh uninstall --app-store."
}

do_uninstall_app_store() {
    local app=""
    [[ -f "$APPSTORE_STATE/install.info" ]] && app=$(sed -n 's/^app=//p' "$APPSTORE_STATE/install.info")
    [[ -n "$app" ]] || app="${GAME:h}/$APPSTORE_LAUNCHER_NAME.app"
    [[ -f "$APPSTORE_STATE/install.info" || -d "$app" ]] || die "KMRP is not installed for the Mac App Store's game."
    refuse_if_running
    say "Removing KMRP's app for the Mac App Store's game ($app)"
    confirm "Uninstall KMRP?" || die "cancelled"
    if [[ -d "$app" ]]; then
        appstore_launcher_is_ours "$app" || die "$app is not KMRP's app; it is left alone."
        rm -rf "$app"
    fi
    rm -rf "$APPSTORE_STATE"
    rmdir "$STATE_ROOT" 2>/dev/null || true
    say "KMRP removed. The game was never changed. What KMRP unpacked while the game ran is in the game's own data (~/Library/Containers/$APPSTORE_BUNDLE_ID/Data/Library/Caches/KMRP), which macOS keeps closed to this installer; it is unused, and deleting the game deletes it."
}

do_status_app_store() {
    if [[ -f "$APPSTORE_STATE/install.info" ]]; then
        cat "$APPSTORE_STATE/install.info"
        local app; app=$(sed -n 's/^app=//p' "$APPSTORE_STATE/install.info")
        if [[ ! -d "$app" ]]; then say "KMRP's app is missing: $app (install again)"
        elif ! codesign --verify --strict "$app" 2>/dev/null; then say "KMRP's app was changed since install: $app (install again)"
        else say "KMRP's app: $app, as installed"; fi
        local now; now=$(sha "$EXE" 2>/dev/null || true)
        [[ "$now" == "$APPSTORE_EXE_SHA" ]] || say "KOTOR_Exe is no longer the version KMRP was made for (1.4.1): the game runs without KMRP until KMRP is updated."
    else
        say "KMRP is not installed."
        say "game: $GAME"
        if [[ "$(sha "$EXE")" == "$APPSTORE_EXE_SHA" ]]; then
            if [[ -f "$PAYLOAD/appstore/loader.dylib" ]]; then say "KOTOR_Exe: the Mac App Store's game, 1.4.1 (supported: KMRP is added as an app beside it; the game is not changed)"
            else say "KOTOR_Exe: the Mac App Store's game, 1.4.1 (this package was built without it)"; fi
        else
            say "KOTOR_Exe: the Mac App Store's game, in a version KMRP was not made for"
        fi
    fi
}

# ---------------------------------------------------------------------- main
[[ $# -ge 1 ]] || { sed -n '2,7p' "$0"; exit 2; }
command=$1; shift
while (( $# )); do
    case "$1" in
        --game) GAME=${2:?--game needs a path}; shift ;;
        --app-store) APPSTORE=1 ;;
        --no-map-notes) MAP_NOTES=0 ;;
        --no-hd-icons) HD_ICONS=0 ;;
        --no-marked-empty) MARKED_EMPTY=0 ;;
        --no-controller) CONTROLLER=0 ;;
        --high-fps) HIGH_FPS=1 ;;
        --no-high-fps) HIGH_FPS=0 ;;
        --keep-anti-aliasing) KEEP_AA=1 ;;
        --debug-logs) DEBUG_LOGS=1 ;;
        --no-prepare) PREPARE=0 ;;
        --resolution)
            RESOLUTION=${2:?--resolution needs current or native}; shift
            [[ "$RESOLUTION" == current ]] && RESOLUTION=half   # the resolution macOS is set to
            [[ "$RESOLUTION" == (native|half) ]] || die "--resolution is current (or half) or native, not $RESOLUTION" ;;
        --size)
            SIZE=${2:?--size needs <width>x<height>}; shift
            [[ "$SIZE" == <->x<-> ]] && (( ${SIZE%x*} >= 640 && ${SIZE#*x} >= 480 )) ||
                die "--size is <width>x<height>, at least 640x480, not $SIZE" ;;
        --yes|-y) ASSUME_YES=1 ;;
        --brief) BRIEF=1 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done
# Global, not inside do_install: zsh runs a trap set in a function when that function
# returns, and it must run when the shell exits mid-install. ZERR as well as EXIT: when
# errexit aborts on a failed command, zsh runs ZERR and exits without running EXIT
# (tested 2026-09-29); an explicit exit (die) runs EXIT.
choose_patches
trap 'on_exit' EXIT
trap 'on_exit' ZERR
trap 'exit 1' INT TERM
case "$command" in
    install) do_install ;;
    uninstall) do_uninstall ;;
    status) do_status ;;
    *) die "unknown command: $command (install, uninstall or status)" ;;
esac
