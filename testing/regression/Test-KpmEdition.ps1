<#
    KMRP installed for KOTOR Patch Manager, and that it makes the same game as the
    standalone.

    The installer can install KMRP for KOTOR Patch Manager instead of with a runtime
    of its own (src/patcher/KpmEdition.cs): when the KOTOR Patch Manager option is on,
    or by itself when KPM's runtime is already in the game folder. It then leaves
    swkotor.exe unmodified and writes kmrp-kpm.dat, which KMRP's module applies in
    memory under KOTOR Patch Manager -- the parts of KMRP Movies and KMRP Map Notes
    only when those patches are ticked there. Until 2026-09-29 this was a separate
    installer, KMRP for KPM, and this file tested that. This proves, per resolution,
    on isolated fixture folders:

      1. the install leaves the executable byte-for-byte unmodified, installs the
         Override files, swkotor.ini's resolution, the data file and SDL, and no
         runtime (no patch_config.toml, KotorPatcher.dll, proxy, ASI loader or
         module);
      2. the data file makes EXACTLY the standalone installer's executable for the
         same resolution: tools/kpm_data.py applies it to the clean executable as the
         module does and compares every byte of the original sections and the
         eleven appended ones with `--apply`'s output -- with all four patches, the
         standalone with the marker fixes on; without Map Notes, the standalone with
         them off; without Movies, the same less exactly the movie sites. The
         install is made with the marker setting OFF, to prove it does not read it;
      3. the Movies and Map Notes parts are exactly the sites they should be: the
         four movie display-mode operands and the movie aspect fit's entry, and the
         .kmn flag;
      4. reinstalling at another resolution replaces the data file;
      5. restore removes every file it installed and leaves the executable as it was;
      6. a game an earlier KMRP patched (with -OlderPatcher, an installer from before
         2026-09-29, which still wrote swkotor.exe; skipped, and said so, without
         it) is restored first and then installed; until 2026-09-29, when this was
         a separate installer, it was refused;
      7. Steam's swkotor.exe (optional input build-inputs\swkotor-steam.exe): the
         install leaves it unmodified and writes the very same data file as for CD
         1.03 at that resolution, byte for byte -- both are built from the originals
         the installer carries -- and restores. Skipped, and said so, without the
         file;
      8. with the option OFF, a folder holding KOTOR Patch Manager's runtime is
         installed for KPM all the same, KPM's files left exactly as they were;
      9. turning the option on over an install with KMRP's own runtime removes that
         runtime, its proxy, K1DC and the 4 GB flag;
     10. once KOTOR Patch Manager has taken that runtime over (its Apply rewrote
         patch_config.toml), reinstalling and restoring leave every runtime file,
         the modules and the flag to KPM.

    "The standalone" is KMRP's installer's --apply, which still writes the
    executable the standalone installer wrote: what the data file must reproduce.
    The installer reads its options from %LOCALAPPDATA%\KMRP\settings.json; this
    copies the player's file aside first and puts it back at the end.

    It does not run the game; the in-game check is tools/kpm_data.py --memory against
    a running game launched through KOTOR Patch Manager.
#>
[CmdletBinding()]
param(
    [string]$Installer    = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$OlderPatcher = ".\build\legacy\KMRP-standalone.exe",
    [string]$CleanExe     = ".\build-inputs\swkotornopatch.exe",
    [string]$SteamExe     = ".\build-inputs\swkotor-steam.exe",
    [string]$SeedIni      = ".\testing\virtual-display\swkotor-7680-windowed.ini",
    [string[]]$Resolutions = @("1920x1080", "3440x1440", "1024x768"),
    [string]$WorkRoot,
    [switch]$KeepWorkRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Restore-TestNvidiaProfiles.ps1")
$script:Failures = 0

function Resolve-Input([string]$path) { return (Resolve-Path -LiteralPath $path).Path }

function Invoke-Exe([string]$exe, [string[]]$arguments) {
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $exe
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    foreach ($argument in $arguments) { [void]$start.ArgumentList.Add($argument) }
    $process = [System.Diagnostics.Process]::Start($start)
    $process.WaitForExit()
    return $process.ExitCode
}

function Assert([bool]$condition, [string]$message) {
    if ($condition) { Write-Host ("  PASS  " + $message) -ForegroundColor Green }
    else { Write-Host ("  FAIL  " + $message) -ForegroundColor Red; $script:Failures++ }
}

function New-Fixture([string]$name, [string]$exe = $CleanExe) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    # A fixture name, so no NVIDIA profile made for it can match a real swkotor.exe.
    Copy-Item -LiteralPath $exe -Destination (Join-Path $folder "kmrp-kpm-selftest.exe")
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    # KMRP's own runtime (Cases 8 and 9) renames the game's binkw32.dll for KOTOR
    # Patch Manager's proxy and puts it back; any bytes stand in for it.
    [IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
    return Join-Path $folder "kmrp-kpm-selftest.exe"
}

# The installer's saved options: the marker fixes, and whether it installs for KOTOR
# Patch Manager.
function Set-Options([bool]$markers, [bool]$patchManager) {
    $m = $markers.ToString().ToLowerInvariant(); $p = $patchManager.ToString().ToLowerInvariant()
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $settingsPath) | Out-Null
    [IO.File]::WriteAllText($settingsPath, "{`r`n  `"driverCompatibility`": true,`r`n  `"markerFixes`": $m,`r`n  `"controllerSupport`": true,`r`n  `"kotorPatchManager`": $p`r`n}`r`n", [Text.UTF8Encoding]::new($false))
}

function Test-Equals([string]$dat, [string]$standaloneExe, [string]$features, [string]$label) {
    python tools\kpm_data.py $dat --clean $CleanExe --equals $standaloneExe --features $features
    Assert ($LASTEXITCODE -eq 0) $label
}

function Get-Sha([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }

$Installer = Resolve-Input $Installer
$CleanExe = Resolve-Input $CleanExe
$SeedIni = Resolve-Input $SeedIni
$cleanHash = Get-Sha $CleanExe
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("kmrp-kpm-" + [Guid]::NewGuid().ToString("N"))
}
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$runtimeFiles = @("patch_config.toml", "KotorPatcher.dll", "binkw32Hooked.dll", "patches", "dinput8.dll",
    "kmrp-controller-runtime.asi", "kmrp-controller.module", "k1-modern-driver-compatibility.asi",
    "KMRP_Controller.manifest")
$settingsPath = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "KMRP\settings.json"
$settingsExisted = Test-Path -LiteralPath $settingsPath
# A copy on disk rather than in memory: it survives this script being stopped.
$settingsCopy = Join-Path $WorkRoot "player-settings.json"
if ($settingsExisted) { Copy-Item -LiteralPath $settingsPath -Destination $settingsCopy }

# Where KMRP Movies and KMRP Map Notes may write: the movie display-mode operands
# (imm32, VA 0x00403D6C, 0x00403D78, 0x005F5B3B, 0x005F5B43), the jump into the movie
# aspect fit (0x004057AC, 7 bytes), and the .kmn enable flag (0x00876000, 4 bytes).
$movieSites = @(@(0x00403D6C, 4), @(0x00403D78, 4), @(0x005F5B3B, 4), @(0x005F5B43, 4), @(0x004057AC, 7))
$cdData = @{}
# A refusal writes KMRP.startup-error.log beside the installer, in dist\, which would
# then ship. One this run creates is removed at the end.
$errorLog = Join-Path (Split-Path -Parent $Installer) "KMRP.startup-error.log"
$errorLogBefore = Test-Path -LiteralPath $errorLog
$steamHash = "34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88"
$laaHash = "CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889"
$SteamExe = if (Test-Path -LiteralPath $SteamExe) { Resolve-Input $SteamExe } else { $null }
# KMRP's .kpatch files as the build wrote them, which the installer carries, and the
# README and licence that go with them (KpmEditionOperations.DeliverKpatches).
$kpatchNames = @("KMRP.kpatch", "KMRP Controller.kpatch", "KMRP Movies.kpatch", "KMRP Map Notes.kpatch")
$kpatchExpected = @{}
foreach ($name in $kpatchNames) { $kpatchExpected[$name] = Get-Sha (Join-Path "build\kmrp\kpm-patches" $name) }
$kpatchExpected["README.txt"] = Get-Sha "src\patcher\KPM-PATCHES-README.txt"
$kpatchExpected["LICENSE-KOTOR-PATCH-MANAGER.txt"] = Get-Sha "third_party\Kotor-Patch-Manager\LICENSE"

# KPM's own settings, parked for the run (Restore-TestNvidiaProfiles.ps1).
$kpmLauncherSettings = Hide-KpmLauncherSettings $WorkRoot
try {
    Write-Host ""
    Write-Host ("KMRP for KOTOR Patch Manager regression  ->  " + $WorkRoot)
    foreach ($resolution in $Resolutions) {
        Write-Host ("Case 1-2  install for KPM at {0}, and the same game as the standalone" -f $resolution)
        $game = New-Fixture ("kpm-" + $resolution)
        $folder = Split-Path -Parent $game
        $dat = Join-Path $folder "kmrp-kpm.dat"
        Set-Options $false $true
        Assert ((Invoke-Exe $Installer @("--in-place", $game, $resolution)) -eq 0) "the install for KPM succeeds (marker setting off)"
        if (Test-Path -LiteralPath $dat) { $cdData[$resolution] = Get-Sha $dat }
        Assert ((Get-Sha $game) -eq $cleanHash) "swkotor.exe is byte-for-byte unmodified"
        foreach ($name in @("kmrp-kpm.dat", "KMRP_KPM.manifest", "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt")) {
            Assert (Test-Path -LiteralPath (Join-Path $folder $name)) ("installed " + $name)
        }
        foreach ($name in $runtimeFiles) {
            Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("no runtime file " + $name)
        }
        Assert ((@(Get-ChildItem -LiteralPath (Join-Path $folder "Override") -File -ErrorAction SilentlyContinue)).Count -gt 1000) "the Override files are installed"
        # KPM has no settings on this PC for the run (Hide-KpmLauncherSettings), so the
        # installer's own copies of KMRP's patches go into the game folder (Case 11 has
        # KPM's own folder).
        $delivered = Join-Path $folder "KPM patches"
        $wrong = @($kpatchNames + @("README.txt", "LICENSE-KOTOR-PATCH-MANAGER.txt") | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $delivered $_)) -or (Get-Sha (Join-Path $delivered $_)) -ne $kpatchExpected[$_] })
        Assert ($wrong.Count -eq 0) ("the four .kpatch files, README and licence are in the game's KPM patches folder, as built (" + ($wrong -join ", ") + ")")
        $width, $height = $resolution -split "x"
        $ini = [IO.File]::ReadAllText((Join-Path $folder "swkotor.ini"))
        Assert ($ini -match "(?m)^Width=$width\r?$" -and $ini -match "(?m)^Height=$height\r?$") "swkotor.ini carries the resolution"

        $standaloneOff = Join-Path $WorkRoot ("standalone-nomarkers-" + $resolution + ".exe")
        Assert ((Invoke-Exe $Installer @("--apply", $CleanExe, $standaloneOff, $resolution)) -eq 0) "the standalone builds its executable, marker fixes off"
        Set-Options $true $true
        $standaloneOut = Join-Path $WorkRoot ("standalone-" + $resolution + ".exe")
        Assert ((Invoke-Exe $Installer @("--apply", $CleanExe, $standaloneOut, $resolution)) -eq 0) "the standalone builds its executable, marker fixes on"
        Test-Equals $dat $standaloneOut "kmrp,kmrp-controller,kmrp-movies,kmrp-map-notes" "all four patches: exactly the standalone's executable"
        Test-Equals $dat $standaloneOff "kmrp,kmrp-movies" "without Map Notes: exactly the standalone's with the marker fixes off"
        Test-Equals $dat $standaloneOut "kmrp,kmrp-map-notes" "without Movies: the standalone's, less the movie sites"
        Test-Equals $dat $standaloneOff "kmrp" "KMRP alone: the standalone's with the marker fixes off, less the movie sites"

        Write-Host ("Case 3  the Movies and Map Notes parts at {0}" -f $resolution)
        $listing = @(python tools\kpm_data.py $dat --list)
        $movieRuns = @($listing | ForEach-Object { if ($_ -match "^\s+movies\s+run\s+0x([0-9a-fA-F]{8})\+(\d+)") { ,@([Convert]::ToInt32($Matches[1], 16), [int]$Matches[2]) } })
        $outside = @($movieRuns | Where-Object { $run = $_; -not ($movieSites | Where-Object { $run[0] -ge $_[0] -and $run[0] + $run[1] -le $_[0] + $_[1] }) })
        $covered = @($movieSites | Where-Object { $site = $_; $movieRuns | Where-Object { $_[0] -ge $site[0] -and $_[0] + $_[1] -le $site[0] + $site[1] } })
        Assert ($movieRuns.Count -gt 0 -and $outside.Count -eq 0) ("every Movies run lies within a movie site ({0} runs)" -f $movieRuns.Count)
        Assert ($covered.Count -eq $movieSites.Count) "every movie site is a Movies run"
        $edits = @($listing | Where-Object { $_ -match "^\s+\S.*\sedit\s" })
        Assert ($edits.Count -eq 1 -and $edits[0] -match "map notes\s+edit\s+0x00876000\+4") "Map Notes is exactly the .kmn flag"
    }

    Write-Host "Case 4  reinstall at another resolution"
    $game = Join-Path (Join-Path $WorkRoot ("kpm-" + $Resolutions[0])) "kmrp-kpm-selftest.exe"
    $folder = Split-Path -Parent $game
    $before = Get-Sha (Join-Path $folder "kmrp-kpm.dat")
    Assert ((Invoke-Exe $Installer @("--in-place", $game, $Resolutions[1])) -eq 0) "reinstall at another resolution succeeds"
    Assert ((Get-Sha (Join-Path $folder "kmrp-kpm.dat")) -ne $before) "the data file was replaced"
    $standaloneOut = Join-Path $WorkRoot ("standalone-" + $Resolutions[1] + ".exe")
    Test-Equals (Join-Path $folder "kmrp-kpm.dat") $standaloneOut "kmrp,kmrp-movies,kmrp-map-notes" "the new data file is the new resolution's"

    Write-Host "Case 5  restore"
    foreach ($resolution in $Resolutions) {
        $game = Join-Path (Join-Path $WorkRoot ("kpm-" + $resolution)) "kmrp-kpm-selftest.exe"
        $folder = Split-Path -Parent $game
        Assert ((Invoke-Exe $Installer @("--restore", $game)) -eq 0) ("restore succeeds (" + $resolution + " fixture)")
        foreach ($name in @("kmrp-kpm.dat", "KMRP_KPM.manifest", "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt")) {
            Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("restore removed " + $name)
        }
        Assert ((@(Get-ChildItem -LiteralPath (Join-Path $folder "Override") -File -ErrorAction SilentlyContinue)).Count -eq 0) "restore emptied Override"
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KPM patches"))) "restore removed the KPM patches folder"
        Assert ((Get-Sha $game) -eq $cleanHash) "swkotor.exe is still unmodified"
    }

    Write-Host "Case 6  a game an earlier KMRP patched is restored, then installed for KPM"
    if (-not (Test-Path -LiteralPath $OlderPatcher)) {
        Write-Host "  SKIPPED  no earlier installer at $OlderPatcher; pass -OlderPatcher" -ForegroundColor DarkYellow
    } else {
        $OlderPatcher = Resolve-Input $OlderPatcher
        $gold = New-Fixture "standalone-installed"
        Assert ((Invoke-Exe $OlderPatcher @("--in-place", $gold, $Resolutions[0])) -eq 0) "the earlier installer installs"
        Assert ((Get-Sha $gold) -ne $cleanHash) "it rewrote swkotor.exe"
        Assert ((Invoke-Exe $Installer @("--in-place", $gold, $Resolutions[0])) -eq 0) "the install for KPM replaces it"
        Assert ((Get-Sha $gold) -eq $cleanHash) "swkotor.exe is the original again"
        Assert (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $gold) "kmrp-kpm.dat")) "and the data file is installed"
        Assert (-not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $gold) "KMRP_Controller.manifest"))) "and the earlier runtime is gone"
        Assert ((Invoke-Exe $Installer @("--restore", $gold)) -eq 0) "restore succeeds"
    }

    Write-Host "Case 7  Steam's swkotor.exe"
    if (-not $SteamExe) {
        Write-Host "  SKIPPED  no build-inputs\swkotor-steam.exe; the Steam case did not run" -ForegroundColor DarkYellow
    } elseif ((Get-Sha $SteamExe) -ne $steamHash) {
        Assert $false "build-inputs\swkotor-steam.exe is Steam's unmodified swkotor.exe"
    } else {
        $steamGame = New-Fixture "steam" $SteamExe
        $steamFolder = Split-Path -Parent $steamGame
        $steamDat = Join-Path $steamFolder "kmrp-kpm.dat"
        Assert ((Invoke-Exe $Installer @("--in-place", $steamGame, $Resolutions[0])) -eq 0) "the install for KPM succeeds over Steam's executable"
        Assert ((Get-Sha $steamGame) -eq $steamHash) "Steam's executable is byte-for-byte unmodified"
        Assert ((Test-Path -LiteralPath $steamDat) -and (Get-Sha $steamDat) -eq $cdData[$Resolutions[0]]) "its data file is CD 1.03's at the same resolution, byte for byte"
        Assert ((@(Get-ChildItem -LiteralPath (Join-Path $steamFolder "Override") -File -ErrorAction SilentlyContinue)).Count -gt 1000) "the Override files are installed"
        Assert ((Invoke-Exe $Installer @("--restore", $steamGame)) -eq 0) "restore succeeds"
        Assert (-not (Test-Path -LiteralPath $steamDat)) "restore removed the data file"
        Assert ((Get-Sha $steamGame) -eq $steamHash) "Steam's executable is still unmodified"
    }

    Write-Host "Case 8  option off, but KOTOR Patch Manager's runtime in the folder: installed for KPM"
    Set-Options $true $false
    $shared = New-Fixture "kpm-with-runtime"
    $sharedFolder = Split-Path -Parent $shared
    # What KOTOR Patch Manager's proxy deployment leaves beside the game after Apply.
    Move-Item -LiteralPath (Join-Path $sharedFolder "binkw32.dll") -Destination (Join-Path $sharedFolder "binkw32Hooked.dll")
    foreach ($name in @("binkw32.dll", "KotorPatcher.dll", "patch_config.toml")) {
        [IO.File]::WriteAllText((Join-Path $sharedFolder $name), "KOTOR Patch Manager's " + $name + "`r`n")
    }
    $kpmFiles = @{}
    foreach ($name in @("binkw32.dll", "binkw32Hooked.dll", "KotorPatcher.dll", "patch_config.toml")) { $kpmFiles[$name] = Get-Sha (Join-Path $sharedFolder $name) }
    Assert ((Invoke-Exe $Installer @("--in-place", $shared, $Resolutions[0])) -eq 0) "the install succeeds"
    $changed = @($kpmFiles.Keys | Where-Object { (Get-Sha (Join-Path $sharedFolder $_)) -ne $kpmFiles[$_] })
    Assert ($changed.Count -eq 0) ("KOTOR Patch Manager's files are exactly as they were (" + ($changed -join ", ") + ")")
    Assert ((Get-Sha $shared) -eq $cleanHash) "swkotor.exe is unmodified"
    Assert (Test-Path -LiteralPath (Join-Path $sharedFolder "kmrp-kpm.dat")) "KMRP's data file is installed"
    Assert (-not (Test-Path -LiteralPath (Join-Path $sharedFolder "patches"))) "no module of KMRP's own"
    Assert ((Invoke-Exe $Installer @("--restore", $shared)) -eq 0) "restore succeeds"
    $changed = @($kpmFiles.Keys | Where-Object { (Get-Sha (Join-Path $sharedFolder $_)) -ne $kpmFiles[$_] })
    Assert ($changed.Count -eq 0) "and leaves KOTOR Patch Manager's files as they were"

    Write-Host "Case 9  the option turned on over KMRP's own runtime: the runtime, K1DC and the flag go"
    Set-Options $true $false
    $switch = New-Fixture "switch-to-kpm"
    $switchFolder = Split-Path -Parent $switch
    $standIn = Get-Sha (Join-Path $switchFolder "binkw32.dll")
    Assert ((Invoke-Exe $Installer @("--in-place", $switch, $Resolutions[0])) -eq 0) "the install with KMRP's own runtime succeeds, driver compatibility on"
    Assert (Test-Path -LiteralPath (Join-Path $switchFolder "k1-modern-driver-compatibility.asi")) "with K1DC"
    Set-Options $true $true
    Assert ((Invoke-Exe $Installer @("--in-place", $switch, $Resolutions[0])) -eq 0) "the install for KPM replaces it"
    foreach ($name in @("KotorPatcher.dll", "patch_config.toml", "kpm_install_state.json", "binkw32Hooked.dll", "patches", "dinput8.dll", "k1-modern-driver-compatibility.asi")) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $switchFolder $name))) ("gone: " + $name)
    }
    Assert (@(Get-ChildItem -LiteralPath $switchFolder -Filter "*.backup.*").Count -eq 0) "gone: the KPM backup and its metadata"
    Assert ((Get-Sha (Join-Path $switchFolder "binkw32.dll")) -eq $standIn) "binkw32.dll is the game's again"
    Assert ((Get-Sha $switch) -eq $cleanHash) "swkotor.exe is the original, the flag cleared"
    Assert (Test-Path -LiteralPath (Join-Path $switchFolder "kmrp-kpm.dat")) "the data file is installed"
    Assert ((Invoke-Exe $Installer @("--restore", $switch)) -eq 0) "and restores"

    # KOTOR Patch Manager's Apply over an install with KMRP's own runtime: it restores
    # the newest backup, KMRP's, and deletes it, backs the unmodified executable up as
    # its own and sets the 4 GB flag again from KMRP.kpatch's static hook; it rewrites
    # patch_config.toml, stages its own KotorPatcher.dll, and extracts KMRP's modules
    # again, byte for byte the ones KMRP installed. The runtime is KPM's from then on.
    Write-Host "Case 10  KOTOR Patch Manager took over KMRP's runtime: reinstall and restore leave it to KPM"
    Set-Options $true $false
    $takeover = New-Fixture "kpm-took-over"
    $takeoverFolder = Split-Path -Parent $takeover
    Assert ((Invoke-Exe $Installer @("--in-place", $takeover, $Resolutions[0])) -eq 0) "the install with KMRP's own runtime succeeds"
    $ours = @(Get-ChildItem -LiteralPath $takeoverFolder -Filter "kmrp-kpm-selftest.exe.backup.*" -File | Where-Object { $_.Extension -ne ".json" })
    Assert ($ours.Count -eq 1 -and (Get-Sha $ours[0].FullName) -eq $cleanHash) "the install left KPM a backup of the unmodified executable"
    # The executable ends as it was, the unmodified file with the same flag; the
    # backup of the unmodified file is KPM's own now, under a name of its own.
    $kpmBackup = "kmrp-kpm-selftest.exe.backup.20260101_000000"
    Move-Item -LiteralPath $ours[0].FullName -Destination (Join-Path $takeoverFolder $kpmBackup)
    Move-Item -LiteralPath ($ours[0].FullName + ".json") -Destination (Join-Path $takeoverFolder ($kpmBackup + ".json"))
    [IO.File]::AppendAllText((Join-Path $takeoverFolder ($kpmBackup + ".json")), "`r`n")
    [IO.File]::AppendAllText((Join-Path $takeoverFolder "patch_config.toml"), "# regenerated by KOTOR Patch Manager`r`n")
    [IO.File]::WriteAllText((Join-Path $takeoverFolder "KotorPatcher.dll"), "KOTOR Patch Manager's own KotorPatcher.dll`r`n")
    [IO.File]::AppendAllText((Join-Path $takeoverFolder "kpm_install_state.json"), "`r`n")
    $kpmFiles = @{}
    foreach ($name in @("patch_config.toml", "KotorPatcher.dll", "kpm_install_state.json", $kpmBackup, ($kpmBackup + ".json"), "binkw32.dll", "binkw32Hooked.dll", "patches\kmrp.dll", "patches\kmrp-movies.dll", "patches\kmrp-controller.dll")) {
        $kpmFiles[$name] = Get-Sha (Join-Path $takeoverFolder $name)
    }
    Assert ((Invoke-Exe $Installer @("--in-place", $takeover, $Resolutions[1])) -eq 0) "reinstalling at another resolution succeeds"
    $changed = @($kpmFiles.Keys | Where-Object { -not (Test-Path -LiteralPath (Join-Path $takeoverFolder $_)) -or (Get-Sha (Join-Path $takeoverFolder $_)) -ne $kpmFiles[$_] })
    Assert ($changed.Count -eq 0) ("KOTOR Patch Manager's runtime, config and modules are all still there, unchanged (" + ($changed -join ", ") + ")")
    Assert ((Get-Sha $takeover) -eq $laaHash) "the 4 GB flag, KPM's now, is left"
    Assert (Test-Path -LiteralPath (Join-Path $takeoverFolder "kmrp-kpm.dat")) "the new resolution's data file is installed"
    Assert (-not ([IO.File]::ReadAllText((Join-Path $takeoverFolder "KMRP_KPM.manifest")) -match "(?m)^(moved|laa)\t")) "the install is now one for KPM"
    Assert ((Invoke-Exe $Installer @("--restore", $takeover)) -eq 0) "restore succeeds"
    $changed = @($kpmFiles.Keys | Where-Object { -not (Test-Path -LiteralPath (Join-Path $takeoverFolder $_)) -or (Get-Sha (Join-Path $takeoverFolder $_)) -ne $kpmFiles[$_] })
    Assert ($changed.Count -eq 0) "restore leaves KOTOR Patch Manager's runtime too"
    Assert (-not (Test-Path -LiteralPath (Join-Path $takeoverFolder "kmrp-kpm.dat"))) "restore removes KMRP's data file"

    # KOTOR Patch Manager's app keeps its patch folder in its settings, "PatchesPath",
    # written by System.Text.Json: backslashes escaped, and anything outside ASCII as
    # \uXXXX, which this folder's name has. The folder already holds an older
    # KMRP.kpatch, which an install brings up to this version and restore leaves, and
    # someone else's file named KMRP Movies.kpatch, which is left alone.
    Write-Host "Case 11  KOTOR Patch Manager's patch folder: KMRP's patches go there, for either install"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $kpmPatchDir = Join-Path $WorkRoot ("kpm-app-patches-" + [char]0x00E9)
    New-Item -ItemType Directory -Force -Path $kpmPatchDir | Out-Null
    foreach ($seed in @(@("KMRP.kpatch", "kmrp"), @("KMRP Movies.kpatch", "someone-elses-movies"))) {
        $staging = Join-Path $WorkRoot ("kpatch-" + $seed[1])
        New-Item -ItemType Directory -Force -Path $staging | Out-Null
        [IO.File]::WriteAllText((Join-Path $staging "manifest.toml"), "[patch]`nid = `"$($seed[1])`"`nversion = `"0.9.0`"`n")
        [IO.Compression.ZipFile]::CreateFromDirectory($staging, (Join-Path $kpmPatchDir $seed[0]))
    }
    $foreignHash = Get-Sha (Join-Path $kpmPatchDir "KMRP Movies.kpatch")
    $kpmSettingsPath = Get-KpmLauncherSettingsPath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $kpmSettingsPath) | Out-Null
    $escaped = ($kpmPatchDir -replace '\\', '\\') -replace ([string][char]0x00E9), 'é'
    [IO.File]::WriteAllText($kpmSettingsPath, "{`r`n  `"GamePath`": `"`",`r`n  `"PatchesPath`": `"$escaped`",`r`n  `"CheckedPatchIds`": []`r`n}", [Text.UTF8Encoding]::new($false))

    Set-Options $true $false
    $appGame = New-Fixture "kpm-app-folder"
    $appFolder = Split-Path -Parent $appGame
    Assert ((Invoke-Exe $Installer @("--in-place", $appGame, $Resolutions[0])) -eq 0) "the install with KMRP's own runtime succeeds"
    foreach ($name in @("KMRP.kpatch", "KMRP Controller.kpatch", "KMRP Map Notes.kpatch")) {
        Assert ((Test-Path -LiteralPath (Join-Path $kpmPatchDir $name)) -and (Get-Sha (Join-Path $kpmPatchDir $name)) -eq $kpatchExpected[$name]) ("KPM's patch folder has " + $name + " as built")
    }
    Assert ((Get-Sha (Join-Path $kpmPatchDir "KMRP Movies.kpatch")) -eq $foreignHash) "someone else's KMRP Movies.kpatch is left alone"
    Assert (-not (Test-Path -LiteralPath (Join-Path $appFolder "KPM patches"))) "no KPM patches folder in the game folder"
    Assert ((Invoke-Exe $Installer @("--restore", $appGame)) -eq 0) "restore succeeds"
    Assert (-not (Test-Path -LiteralPath (Join-Path $kpmPatchDir "KMRP Controller.kpatch")) -and
            -not (Test-Path -LiteralPath (Join-Path $kpmPatchDir "KMRP Map Notes.kpatch"))) "restore removes the patches the install added"
    Assert ((Get-Sha (Join-Path $kpmPatchDir "KMRP.kpatch")) -eq $kpatchExpected["KMRP.kpatch"]) "and keeps the KMRP.kpatch that was there, at this version"
    Assert ((Get-Sha (Join-Path $kpmPatchDir "KMRP Movies.kpatch")) -eq $foreignHash) "and someone else's file"

    Set-Options $true $true
    Assert ((Invoke-Exe $Installer @("--in-place", $appGame, $Resolutions[0])) -eq 0) "the install for KPM succeeds"
    Assert ((Test-Path -LiteralPath (Join-Path $kpmPatchDir "KMRP Controller.kpatch")) -and
            (Get-Sha (Join-Path $kpmPatchDir "KMRP Controller.kpatch")) -eq $kpatchExpected["KMRP Controller.kpatch"]) "for KPM too, the patches go into KPM's folder"
    Assert (-not (Test-Path -LiteralPath (Join-Path $appFolder "KPM patches"))) "and not into the game folder"
    Assert ((Invoke-Exe $Installer @("--restore", $appGame)) -eq 0) "and restores"
    Assert (-not (Test-Path -LiteralPath (Join-Path $kpmPatchDir "KMRP Controller.kpatch"))) "restore removes them again"

    Write-Host "Case 12  --export-kpm-patches writes the set out, for sharing"
    $exportDir = Join-Path $WorkRoot "exported patches"
    Assert ((Invoke-Exe $Installer @("--export-kpm-patches", $exportDir)) -eq 0) "the export succeeds"
    $wrong = @($kpatchExpected.Keys | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $exportDir $_)) -or (Get-Sha (Join-Path $exportDir $_)) -ne $kpatchExpected[$_] })
    Assert ($wrong.Count -eq 0) ("the four .kpatch files, README and licence, as built (" + ($wrong -join ", ") + ")")
}
finally {
    Restore-KpmLauncherSettings $kpmLauncherSettings
    if ((Test-Path -LiteralPath $errorLog) -and -not $errorLogBefore) { Remove-Item -LiteralPath $errorLog -Force }
    if ($settingsExisted) { Copy-Item -LiteralPath $settingsCopy -Destination $settingsPath -Force }
    elseif (Test-Path -LiteralPath $settingsPath) { Remove-Item -LiteralPath $settingsPath -Force }
    Restore-TestNvidiaProfiles $WorkRoot
    if (-not $KeepWorkRoot) { Remove-TestDpiValues $WorkRoot }
    if (-not $KeepWorkRoot -and (Test-Path -LiteralPath $WorkRoot)) {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $WorkRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a test directory outside the system temp root: $WorkRoot"
        }
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
}

if ($script:Failures -ne 0) { throw "$($script:Failures) KMRP for KOTOR Patch Manager check(s) failed." }
Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
