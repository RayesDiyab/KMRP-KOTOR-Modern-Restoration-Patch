#!/bin/zsh
# KMRP for macOS -- installer, uninstaller and status.
#
#   kmrp-mac.sh install   [--game "<path>/Knights of the Old Republic.app"] [--no-map-notes]
#                         [--no-controller] [--debug-logs]
#                         [--resolution current|native | --size <W>x<H>] [--yes]
#   kmrp-mac.sh uninstall [--game ...] [--yes]
#   kmrp-mac.sh status    [--game ...] [--brief]
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
#      KPM's own records (kpm_install_state.json, KOTOR_Exe.backup.<time>) and kmrp.kpatch in
#      KPM's patch folder, so KPM recognises the install, as on Windows.
#   3. Picks the resolution the game starts at: the display's size, and on a Retina display
#      native (every pixel, e.g. 3024x1964) or half (the point size, e.g. 1512x982, which macOS
#      scales up). Writes it as Width and Height to [Graphics Options] in swkotor.ini (a size
#      the display does not offer, given with --size, as ForceWidth and ForceHeight). In the
#      game, Options, Graphics changes it at any time. And, beside swkotor.ini,
#      kmrp-controller.ini with the controller's default settings unless the player already
#      has one.
#   4. Nothing goes into the game's override folder, since 2026-10-04: the menu set for every
#      resolution, KMRP's artwork and SDL are inside the patch's module (patches/kmrp-assets),
#      which unpacks what the resolution needs to ~/Library/Caches/KMRP when the game starts,
#      blends a set for a size the build has none for, and makes from the player's own game
#      what KMRP builds from its art and data. Until then this installer did all of that and
#      wrote some 1,800 files into Contents/Assets/override.
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
ASPYR_PREFS="$HOME/Library/Preferences/com.aspyr.kotor.steam.plist"

GAME=""
MAP_NOTES=1
CONTROLLER=1   # KMRP's controller support: the module, SDL and its settings file (Windows' option too)
DEBUG_LOGS=0   # the module's diagnostic log (Windows' third option, off unless asked for)
RESOLUTION=""
SIZE=""
ASSUME_YES=0
BRIEF=0   # status without checking each installed file (KMRP Installer's view)
BACKUP_SEQ=0
INSTALLING=0
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
    TEXTURE_PACK="$GAME/Contents/Assets/TexturePacks/swpc_tex_gui.erf"
    OPTIONS_INI="$MACOS/configs/kmrp.ini"
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
# (the sets themselves are inside the patch's module). For any other size the module blends one
# from the nearest set, when kmrp-guiblend's table covers the size.
listed_sizes() {
    tr -d '\r' < "$PAYLOAD/sizes.txt" 2>/dev/null | grep -E '^[0-9]+x[0-9]+$'
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
# untouched, and kmrp.kpatch where KPM finds it, for the player to tick in KPM. KMRP's
# uninstall leaves the untouched game; FTD's patch is not put back.
#
# And KMRP's own install is one KPM recognises and takes over, as on Windows (KpmState,
# WriteKpmBackup, DeliverKpatches): kpm_install_state.json with the game's identity, a copy of
# the untouched KOTOR_Exe in KPM's format beside it, from which KPM's Apply starts, and
# kmrp.kpatch in KPM's patch folder. Uninstall leaves the runtime to KPM once KPM's Apply has
# rewritten patch_config.toml (Restore, ConfigChangedSinceInstall).
# addresses.db: KPM's Apply copies its address database beside the game (PatchApplicator) and
# its Remove deletes it (PatchRemover), as with the rest.
KPM_FILES=(KotorPatcher.dylib patch_config.toml patches kpm_install_state.json addresses.db)
FTD_PATCHES=(k1widescreenpatch k1-stray-bug-fixes-patch)
# What this installer installs, since 2026-10-04: KMRP's own patch and the two of FTD's it
# requires (until then KMRP's one patch carried a copy of them). The package's file for each and
# the patch's id, which is also the name KPM gives its module in patches/. In KPM's order: a patch
# after the ones it requires.
KPATCH_FILES=(K1StrayBugFixes.kpatch K1WidescreenPatch.kpatch kmrp.kpatch)
KPATCH_IDS=(k1-stray-bug-fixes-patch k1widescreenpatch kmrp)
KPM_ORIGINAL=""   # the untouched game, when an install is to be replaced
KPM_PROBLEM=""    # why it cannot be, otherwise
KPM_OTHERS=""     # the other patches KPM has installed, when KMRP installs for KPM
KPATCH_FOLDER=""  # where kmrp.kpatch went
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

kpatch_is_kmrp() { unzip -p "$1" manifest.toml 2>/dev/null | grep -q '^id = "kmrp"$'; }

# The Widescreen Patch KMRP needs has the entry points KMRP asks for its .gui mode by
# (K1Widescreen_UseGuiFileLayouts; FTD's patch has them from its 2026-10-04 adjustment).
kpatch_has_entry_points() {
    unzip -p "$1" binaries/macos_x86_64.dylib 2>/dev/null | grep -qa K1Widescreen_UseGuiFileLayouts
}

deliver_kpatch() {   # deliver_kpatch <for_kpm>: the three .kpatch files into KPM's patch folder
    local folder file src target state
    if [[ ! -f "$PAYLOAD/engine/kmrp.kpatch" ]]; then
        warn "the package has no kmrp.kpatch; KotOR Patch Manager will not list KMRP"
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
    for file in $KPATCH_FILES; do
        src="$PAYLOAD/engine/$file"; target="$folder/$file"; state=created
        [[ -f "$src" ]] || continue
        if [[ -e "$target" ]]; then
            [[ "$(sha "$target")" == "$(sha "$src")" ]] && continue   # already there: not KMRP's to remove
            case "$file" in
                kmrp.kpatch)
                    if ! kpatch_is_kmrp "$target"; then warn "left $target alone: it is not KMRP's"; continue; fi
                    state=replaced ;;   # an older KMRP's: brought up to this version, and left at uninstall
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
    [[ "$1" == "$OPTIONS_INI" || "$1" == "${OPTIONS_INI:h}" ]] && return 0
    [[ "${1:h}" == "$MACOS/patches" || "$1" == "$MACOS/patches" ]]
}

kpm_backups() {   # KPM's copies of the game and their .json, newest first
    print -rl -- "$MACOS"/KOTOR_Exe.backup.*(Nom)
}

kpm_present() {   # 0 when KotOR Patch Manager left anything beside KOTOR_Exe
    local f
    for f in $KPM_FILES; do [[ -e "$MACOS/$f" ]] && return 0; done
    [[ -n "$(kpm_backups)" ]]
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
    # What KPM's own removal does with the options it recorded (PatchOptionsIni.RemoveSections).
    options_remove
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

options_write() {   # the section first, then whatever else the file held
    local made_dir=0 existed=0 rest
    [[ -d "${OPTIONS_INI:h}" ]] || { mkdir "${OPTIONS_INI:h}"; made_dir=1; }
    [[ -f "$OPTIONS_INI" ]] && existed=1
    rest=$(options_rest; print -n x); rest=${rest%x}
    {
        printf '[Patch Options]\r\ncontroller=%d\r\nmap-notes=%d\r\ndebug-logs=%d\r\n' $CONTROLLER $MAP_NOTES $DEBUG_LOGS
        [[ -n "$rest" ]] && printf '\r\n%s' "$rest"
    } > "$OPTIONS_INI.kmrp-tmp"
    mv -f "$OPTIONS_INI.kmrp-tmp" "$OPTIONS_INI"
    (( made_dir )) && record dir "${OPTIONS_INI:h}" "-" "-"
    record options "$OPTIONS_INI" "-" "$existed"
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
    elif [[ "$exe_sha" != "$VANILLA_EXE_SHA" ]]; then
        die "KOTOR_Exe is not the unmodified Steam build this KMRP supports (SHA-256 $exe_sha, expected ${VANILLA_EXE_SHA[1,16]}...). If another patch is installed, remove it first; Steam's 'Verify integrity of game files' restores the original."
    fi
    [[ -f "$TEXTURE_PACK" ]] || die "the game's texture pack is missing: $TEXTURE_PACK"

    choose_resolution
    local size="${WIDTH}x${HEIGHT}" from derived=0
    if listed_sizes | grep -qx "$size"; then
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
    say "Controller support: $([[ $CONTROLLER == 1 ]] && echo on || echo off)"
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
        if (( ! CONTROLLER || ! MAP_NOTES || DEBUG_LOGS )); then
            warn "KotOR Patch Manager installs KMRP here, so KMRP's options are chosen in KPM (with patch options; KPM 0.7.1 installs controller support and map notes, without logs). The choices made in this installer are not applied."
        fi
    else
        say "Backing up KOTOR_Exe..."
        cp -p "$EXE" "$STATE/backup/KOTOR_Exe"
        [[ "$(sha "$STATE/backup/KOTOR_Exe")" == "$VANILLA_EXE_SHA" ]] || die "the backup copy does not match"

        say "Installing the engine patches..."
        install_file "$PAYLOAD/engine/KotorPatcher.dylib" "$MACOS"
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
            if [[ "${KPATCH_IDS[n]}" == kmrp ]]; then
                codesign --verify "$module" || die "the module taken out of ${KPATCH_FILES[n]} is damaged"
            fi
        done
        local hook_list=patch_config.toml
        (( CONTROLLER )) || hook_list=patch_config.controller-off.toml
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
        print -r -- "controller=$CONTROLLER"
        print -r -- "debug_logs=$DEBUG_LOGS"
        print -r -- "for_kpm=$for_kpm"
        print -r -- "kpatch=${KPATCH_FOLDER:--}"
        print -r -- "complete=1"
    } > "$STATE/install.info"
    INSTALLING=0
    rm -rf "$WORK"
    if (( for_kpm )); then
        say "Installed for KotOR Patch Manager: the resolution and the controller's settings. KOTOR_Exe was not modified, and nothing was written to the game's override folder: the menus are inside KMRP's patch."
        if [[ -n "$KPATCH_FOLDER" ]]; then
            say "KMRP's patch is in $KPATCH_FOLDER, with FTD's Widescreen Patch and Stray Bug Fixes, which it requires. Open KotOR Patch Manager, tick all three, and press Apply."
        fi
    else
        say "Installed: KMRP's patch, on FTD's Widescreen Patch and Stray Bug Fixes, with the menus for every resolution inside it. Nothing was written to the game's override folder. The first start of the game unpacks what $size needs, which takes a few seconds."
        say "KOTOR_Exe was modified (one load command, re-signed ad hoc); the original is in $STATE/backup."
        [[ -n "$KPATCH_FOLDER" ]] && say "KMRP's patch is also in KotOR Patch Manager's patch folder ($KPATCH_FOLDER)."
    fi
    say "To undo everything: Uninstall in KMRP Installer, or kmrp-mac.sh uninstall."
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
    local quiet=${1:-0} kept=0 kind target recorded backup now over=0
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
            options)
                options_remove ;;
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
    return $kept
}

kpm_holds_only_kmrp() {   # config, InstalledPatches (including module-less patches), and modules
    # "Only KMRP" is KMRP with the two patches it requires and installs, and nothing else.
    local id module installed patch_state="$MACOS/kpm_install_state.json"
    local count=0
    [[ -f "$MACOS/patch_config.toml" ]] || return 1
    for id in ${(f)"$(sed -n 's/^id = "\(.*\)"$/\1/p' "$MACOS/patch_config.toml")"}; do
        (( ${KPATCH_IDS[(Ie)$id]} )) || return 1
        [[ "$id" == kmrp ]] && (( ++count ))
    done
    (( count > 0 )) || return 1
    if [[ -e "$patch_state" || -L "$patch_state" ]]; then
        # plutil parses JSON; missing/malformed/non-array state must retain the runtime.
        installed=$(plutil -extract InstalledPatches json -o - "$patch_state" 2>/dev/null) || return 1
        [[ "$installed" == \[*\] ]] || return 1
        for id in ${(s:,:)${${installed#\[}%\]}}; do
            id=${${id//[[:space:]]/}//\"/}
            [[ -z "$id" ]] && continue
            (( ${KPATCH_IDS[(Ie)$id]} )) || return 1
        done
    fi
    for module in "$MACOS"/patches/*(N); do
        (( ${KPATCH_IDS[(Ie)${module:t:r}]} )) || return 1
    done
    return 0
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
        if kpm_present; then
            local check=0
            kpm_check || check=$?
            case $check in
                0) say "KOTOR_Exe: FTD's widescreen patch through KotOR Patch Manager (supported: KMRP replaces it)" ;;
                2) say "KOTOR_Exe: managed by KotOR Patch Manager ($KPM_OTHERS; supported: KMRP installs for KPM)" ;;
                *) say "KOTOR_Exe: a KotOR Patch Manager install KMRP cannot replace ($KPM_PROBLEM)" ;;
            esac
        elif [[ "$(sha "$EXE")" == "$VANILLA_EXE_SHA" ]]; then say "KOTOR_Exe: unmodified Steam build (supported)"
        else say "KOTOR_Exe: modified or a different build"; fi
        (( BRIEF )) && return 0
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
        --no-controller) CONTROLLER=0 ;;
        --debug-logs) DEBUG_LOGS=1 ;;
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
trap 'on_exit' EXIT
trap 'on_exit' ZERR
trap 'exit 1' INT TERM
case "$command" in
    install) do_install ;;
    uninstall) do_uninstall ;;
    status) do_status ;;
    *) die "unknown command: $command (install, uninstall or status)" ;;
esac
