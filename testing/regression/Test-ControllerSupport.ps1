<#
    KMRP's installer on KOTOR Patch Manager's runtime: what it installs, how the
    options change it, what it refuses, and that restore takes it all back.

    Since 2026-09-29 KMRP's installer installs KOTOR Patch Manager's runtime itself,
    laid out as KPM's own proxy deployment lays out a game folder: the proxy as
    binkw32.dll with the game's own renamed binkw32Hooked.dll, KotorPatcher.dll,
    patch_config.toml, and KMRP's four patches' modules under patches\. The options
    choose which patches go in -- the controller option KMRP Controller, the marker
    option KMRP Map Notes -- and whether Synchro's K1DC (its ASI loader and .asi) is
    installed; KMRP and KMRP Movies always are. On CD 1.03 it sets the large-address
    flag, the one change to swkotor.exe; Steam's is never changed. A folder that
    already holds KOTOR Patch Manager's runtime is installed for KPM instead
    (Case 2; the KOTOR Patch Manager option itself is Test-KpmEdition.ps1's).

    Until 2026-09-28 this file tested the controller option alone, and until
    2026-09-29 the standalone installer's runtime: an .asi loaded by K1DC's loader
    with a one-patch patch_config.toml. Its cases are kept where the contract held
    (the player's settings file, the defaults, switching an option), and changed
    where it did not: an unrelated patch_config.toml used to make the runtime step
    decline while the rest installed; now KMRP's executable changes are that
    runtime, so such a folder gets KMRP's install for KOTOR Patch Manager.

    The installer reads its options from %LOCALAPPDATA%\KMRP\settings.json; this
    copies the player's file aside first and puts it back at the end.
#>
[CmdletBinding()]
param(
    [string]$Patcher  = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$CleanExe = ".\build-inputs\swkotornopatch.exe",
    [string]$SteamExe = ".\build-inputs\swkotor-steam.exe",
    [string]$SeedIni  = ".\testing\virtual-display\swkotor-7680-windowed.ini",
    [string]$Resolution = "1920x1080",
    [string]$WorkRoot,
    [switch]$KeepWorkRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Restore-TestNvidiaProfiles.ps1")
$script:Failures = 0

function Resolve-Input([string]$path) { return (Resolve-Path -LiteralPath $path).Path }

function Invoke-Patcher([string[]]$patcherArgs) {
    $start = [System.Diagnostics.ProcessStartInfo]::new()
    $start.FileName = $Patcher
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    foreach ($argument in $patcherArgs) { [void]$start.ArgumentList.Add($argument) }
    $process = [System.Diagnostics.Process]::Start($start)
    $process.WaitForExit()
    return $process.ExitCode
}

function Assert([bool]$condition, [string]$message) {
    if ($condition) { Write-Host ("  PASS  " + $message) -ForegroundColor Green }
    else { Write-Host ("  FAIL  " + $message) -ForegroundColor Red; $script:Failures++ }
}

function Get-Sha([string]$path) { return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }

# A fixture game folder: the executable under a fixture name (so no NVIDIA profile
# or DPI value made for it can match a real swkotor.exe), swkotor.ini, and a
# stand-in binkw32.dll, which the installer only renames and puts back.
function New-Install([string]$name, [string]$exe = $CleanExe) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    Copy-Item -LiteralPath $exe -Destination (Join-Path $folder "kmrp-controller-selftest.exe")
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    [IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
    return Join-Path $folder "kmrp-controller-selftest.exe"
}

function Set-TestOptions([bool]$driver, [bool]$markers, [bool]$controller) {
    $d = $driver.ToString().ToLowerInvariant(); $m = $markers.ToString().ToLowerInvariant()
    $c = $controller.ToString().ToLowerInvariant()
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $settingsPath) | Out-Null
    [IO.File]::WriteAllText($settingsPath, "{`r`n  `"driverCompatibility`": $d,`r`n  `"markerFixes`": $m,`r`n  `"controllerSupport`": $c`r`n}`r`n", [Text.UTF8Encoding]::new($false))
}

# The installed patch_config.toml must list exactly these patches, in this order,
# each with exactly its hooks from src/controller-native/kotor1.hooks.toml and its
# own module (kmrp_controller.engine_config_problems, every runtime field compared).
function Assert-Config([string]$folder, [string[]]$ids, [string]$targetSha, [string]$label) {
    $config = Join-Path $folder "patch_config.toml"
    python -c "import sys; sys.path.insert(0,'tools'); import kmrp_controller as k; p=k.engine_config_problems(sys.argv[1], sys.argv[3].split(','), sys.argv[2]); print(*p, sep='\n') if p else None; sys.exit(1 if p else 0)" $config $targetSha ($ids -join ",")
    Assert ($LASTEXITCODE -eq 0) $label
    python tools\check_module_exports.py $config (Join-Path $folder "patches\kmrp.dll")
    Assert ($LASTEXITCODE -eq 0) "the installed module exports every hooked function"
}

$Patcher = Resolve-Input $Patcher
$CleanExe = Resolve-Input $CleanExe
$SeedIni = Resolve-Input $SeedIni
$SteamExe = if (Test-Path -LiteralPath $SteamExe) { Resolve-Input $SteamExe } else { $null }
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("kmrp-controller-" + [Guid]::NewGuid().ToString("N"))
}
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

$cleanHash = Get-Sha $CleanExe
$laaHash = "CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889"
$steamHash = "34E6D971C034222A417995D8E1E8FDD9F8781795C9C289BD86C499A439F34C88"
$standInHash = $null
$moduleHash = Get-Sha "src\controller-native\kmrp-controller.module"
$runtimeHash = Get-Sha "build\kpm-runtime\KotorPatcher.dll"
$proxyHash = Get-Sha "build\kpm-runtime\binkw32.dll"
# kpm_install_state.json tells KOTOR Patch Manager the flagged CD 1.03 executable is
# still CD 1.03, and that the proxy is installed (Steam's gets one too; Case 9).
$engineFiles = @("KotorPatcher.dll", "patch_config.toml", "binkw32Hooked.dll", "patches\kmrp.dll",
    "patches\kmrp-movies.dll", "kmrp-kpm.dat", "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt",
    "kmrp-kotor-patch-manager-LICENSE.txt", "kmrp-controller.ini", "KMRP_KPM.manifest",
    "kpm_install_state.json")
# The standalone installer's runtime, which nothing installs any more.
$retired = @("kmrp-controller-runtime.asi", "kmrp-controller.module", "KMRP_Controller.manifest")
$allIds = @("kmrp", "kmrp-movies", "kmrp-map-notes", "kmrp-controller")

$settingsPath = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "KMRP\settings.json"
$settingsExisted = Test-Path -LiteralPath $settingsPath
# A copy on disk rather than in memory: it survives this script being stopped.
$settingsCopy = Join-Path $WorkRoot "player-settings.json"
if ($settingsExisted) { Copy-Item -LiteralPath $settingsPath -Destination $settingsCopy }
# The refusals this proves write KMRP.startup-error.log beside the installer, in
# dist\, which would then ship. One this run creates is removed at the end.
$errorLog = Join-Path (Split-Path -Parent $Patcher) "KMRP.startup-error.log"
$errorLogBefore = Test-Path -LiteralPath $errorLog

# KPM's own settings, parked for the run (Restore-TestNvidiaProfiles.ps1).
$kpmLauncherSettings = Hide-KpmLauncherSettings $WorkRoot
try {
    Set-TestOptions $true $true $true
    Write-Host ""
    Write-Host ("KMRP installer regression  ->  " + $WorkRoot)
    Write-Host "Case 1  install and restore, every option on"
    $game = New-Install "standard"
    $folder = Split-Path -Parent $game
    $standInHash = Get-Sha (Join-Path $folder "binkw32.dll")
    Assert ((Invoke-Patcher @("--in-place", $game, $Resolution)) -eq 0) "the install succeeds"
    foreach ($name in $engineFiles + @("patches\kmrp-controller.dll", "dinput8.dll", "k1-modern-driver-compatibility.asi")) {
        Assert (Test-Path -LiteralPath (Join-Path $folder $name)) ("installed " + $name)
    }
    foreach ($name in $retired) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("no standalone runtime file " + $name)
    }
    Assert ((Get-Sha (Join-Path $folder "binkw32.dll")) -eq $proxyHash) "binkw32.dll is KOTOR Patch Manager's proxy, as built"
    Assert ((Get-Sha (Join-Path $folder "binkw32Hooked.dll")) -eq $standInHash) "the game's binkw32.dll was renamed binkw32Hooked.dll, unchanged"
    Assert ((Get-Sha (Join-Path $folder "KotorPatcher.dll")) -eq $runtimeHash) "KotorPatcher.dll is the runtime as built"
    foreach ($id in @("kmrp", "kmrp-movies", "kmrp-controller")) {
        Assert ((Get-Sha (Join-Path $folder "patches\$id.dll")) -eq $moduleHash) ("patches\$id.dll is kmrp-controller.module")
    }
    Assert-Config $folder $allIds $cleanHash "patch_config.toml lists all four patches, each with exactly its hooks"
    Assert ((Get-Sha $game) -eq $laaHash) "swkotor.exe carries the large-address flag and nothing else"
    # A backup of the unmodified executable, as KOTOR Patch Manager 0.7.1 makes one
    # (BackupManager, BackupInfo): its Apply restores the newest backup first, so it
    # starts from this file and sets the flag itself.
    $backups = @(Get-ChildItem -LiteralPath $folder -Filter "kmrp-controller-selftest.exe.backup.*" -File | Where-Object { $_.Extension -ne ".json" })
    Assert ($backups.Count -eq 1 -and $backups[0].Name -match '^kmrp-controller-selftest\.exe\.backup\.\d{8}_\d{6}$') "one KPM backup, named as KPM names one"
    Assert ((Get-Sha $backups[0].FullName) -eq $cleanHash) "holding the unmodified executable"
    $backupInfo = [IO.File]::ReadAllText($backups[0].FullName + ".json") | ConvertFrom-Json
    Assert ($backupInfo.OriginalPath -eq $game -and $backupInfo.BackupPath -eq $backups[0].FullName -and
            $backupInfo.Hash -eq $cleanHash -and $backupInfo.FileSize -eq 4042752 -and $null -eq $backupInfo.DetectedVersion -and
            (@($backupInfo.InstalledPatches) -join ",") -eq ($allIds -join ",")) "its metadata has KPM's fields: this executable, the backup, the unmodified hash and size, the patches"
    $sdlPath = Join-Path $folder "kmrp-sdl3.dll"
    Assert ((Get-Sha $sdlPath) -eq (Get-Sha 'build/deps/kmrp-sdl3.dll')) "installed SDL matches the pinned dependency"
    # MIT asks for its notice to travel with the runtime and the module it covers.
    Assert ((Get-Sha (Join-Path $folder "kmrp-kotor-patch-manager-LICENSE.txt")) -eq (Get-Sha "third_party\Kotor-Patch-Manager\LICENSE")) "the KOTOR Patch Manager MIT licence is the submodule's"
    $manifest = [IO.File]::ReadAllText((Join-Path $folder "KMRP_KPM.manifest"))
    Assert ($manifest -match "(?m)^moved\tbinkw32\.dll\tbinkw32Hooked\.dll\t$standInHash\r?$") "the manifest records the rename with the game's hash"
    Assert ($manifest -match "(?m)^laa\tset\r?$") "the manifest records the large-address flag"
    # KPM 0.7.1's Apply refuses the flagged executable's hash unless this file names the
    # original; the fields are its ManagedInstallState's.
    $state = [IO.File]::ReadAllText((Join-Path $folder "kpm_install_state.json")) | ConvertFrom-Json
    Assert ($state.OriginalHash -eq $cleanHash -and $state.OriginalFileSize -eq 4042752 -and
            $state.OriginalVersion.Hash -eq $cleanHash -and $state.OriginalVersion.Version -eq "1.0.3") "kpm_install_state.json names CD 1.03 as the original"
    Assert ($state.GameExePath -eq $game -and $state.LibraryProxyInstalled -eq $true) "kpm_install_state.json names this executable and the proxy"
    Assert ((@($state.InstalledPatches) -join ",") -eq ($allIds -join ",")) "kpm_install_state.json lists the four patches"

    Assert ((Invoke-Patcher @("--restore", $game)) -eq 0) "restore succeeds"
    foreach ($name in $engineFiles + @("patches\kmrp-controller.dll", "dinput8.dll", "k1-modern-driver-compatibility.asi")) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("restore removed " + $name)
    }
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "patches"))) "restore removed the empty patches folder"
    Assert (@(Get-ChildItem -LiteralPath $folder -Filter "*.backup.*").Count -eq 0) "restore removed the KPM backup and its metadata"
    Assert ((Get-Sha (Join-Path $folder "binkw32.dll")) -eq $standInHash) "the game's binkw32.dll is back, unchanged"
    Assert ((Get-Sha $game) -eq $cleanHash) "swkotor.exe is byte-for-byte the original"

    # Since 2026-09-29 (later the same day as the first version of this case, which
    # required a refusal) such a folder is installed for KOTOR Patch Manager: KMRP's
    # files only, KPM's left as they are, and the player ticks KMRP's patches there.
    Write-Host ""
    Write-Host "Case 2  another copy of KOTOR Patch Manager's runtime: installed for KPM, KPM's files untouched"
    foreach ($foreign in @("patch_config.toml", "KotorPatcher.dll", "binkw32Hooked.dll")) {
        $conflictGame = New-Install ("foreign-" + $foreign)
        $conflictFolder = Split-Path -Parent $conflictGame
        $sentinel = "# " + $foreign + " belongs to someone else`r`n"
        [IO.File]::WriteAllText((Join-Path $conflictFolder $foreign), $sentinel, [Text.UTF8Encoding]::new($false))
        Assert ((Invoke-Patcher @("--in-place", $conflictGame, $Resolution)) -eq 0) ("with an existing " + $foreign + " the install succeeds")
        Assert ([IO.File]::ReadAllText((Join-Path $conflictFolder $foreign)) -eq $sentinel) ("the existing " + $foreign + " is untouched")
        Assert ((Get-Sha $conflictGame) -eq $cleanHash) "swkotor.exe is untouched"
        Assert ((Get-Sha (Join-Path $conflictFolder "binkw32.dll")) -eq $standInHash) "binkw32.dll is untouched"
        Assert (Test-Path -LiteralPath (Join-Path $conflictFolder "kmrp-kpm.dat")) "KMRP's data file is installed"
        Assert ((@(Get-ChildItem -LiteralPath (Join-Path $conflictFolder "Override") -File -ErrorAction SilentlyContinue)).Count -gt 1000) "the Override files are installed"
        Assert (-not (Test-Path -LiteralPath (Join-Path $conflictFolder "patches"))) "no module of KMRP's own"
        Assert (-not (Test-Path -LiteralPath (Join-Path $conflictFolder "dinput8.dll"))) "no K1DC: KPM has its own"
        $manifest = [IO.File]::ReadAllText((Join-Path $conflictFolder "KMRP_KPM.manifest"))
        Assert (-not ($manifest -match "(?m)^(moved|laa)\t")) "the manifest records no runtime and no 4 GB flag"
        Assert ((Invoke-Patcher @("--restore", $conflictGame)) -eq 0) "restore succeeds"
        Assert ([IO.File]::ReadAllText((Join-Path $conflictFolder $foreign)) -eq $sentinel) ("restore leaves " + $foreign)
        Assert (-not (Test-Path -LiteralPath (Join-Path $conflictFolder "kmrp-kpm.dat"))) "restore removes KMRP's data file"
    }

    Write-Host "Case 3  a file in the way part-way through: the install rolls back"
    $sdlGame = New-Install "sdl-conflict"
    $sdlFolder = Split-Path -Parent $sdlGame
    $foreignSdl = Join-Path $sdlFolder "kmrp-sdl3.dll"
    [IO.File]::WriteAllText($foreignSdl, "foreign SDL sentinel")
    Assert ((Invoke-Patcher @("--in-place", $sdlGame, $Resolution)) -ne 0) "a foreign kmrp-sdl3.dll stops the install"
    Assert ([IO.File]::ReadAllText($foreignSdl) -eq "foreign SDL sentinel") "the foreign SDL is intact"
    Assert ((Get-Sha $sdlGame) -eq $cleanHash) "swkotor.exe is untouched"
    Assert ((Get-Sha (Join-Path $sdlFolder "binkw32.dll")) -eq $standInHash) "binkw32.dll is untouched"
    foreach ($name in @("KotorPatcher.dll", "patch_config.toml", "binkw32Hooked.dll", "kmrp-kpm.dat", "KMRP_KPM.manifest")) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $sdlFolder $name))) ("rolled back: no " + $name)
    }
    Assert ((@(Get-ChildItem -LiteralPath (Join-Path $sdlFolder "Override") -File -ErrorAction SilentlyContinue)).Count -eq 0) "rolled back: Override is empty"

    # The options are independent: the controller option chooses KMRP Controller, the
    # marker option KMRP Map Notes, driver compatibility K1DC's two files.
    Write-Host "Case 4  controller support without driver compatibility"
    Set-TestOptions $false $true $true
    $soloGame = New-Install "controller-only"
    $soloFolder = Split-Path -Parent $soloGame
    Assert ((Invoke-Patcher @("--in-place", $soloGame, $Resolution)) -eq 0) "controller-only install succeeds"
    Assert (-not (Test-Path -LiteralPath (Join-Path $soloFolder "dinput8.dll"))) "no ASI loader: KMRP's runtime does not need it"
    Assert (-not (Test-Path -LiteralPath (Join-Path $soloFolder "k1-modern-driver-compatibility.asi"))) "driver compatibility's payload is not installed"
    Assert-Config $soloFolder $allIds $cleanHash "all four patches"
    Assert ((Invoke-Patcher @("--restore", $soloGame)) -eq 0) "controller-only restore succeeds"

    Write-Host "Case 5  driver compatibility without controller support"
    Set-TestOptions $true $true $false
    $driverGame = New-Install "driver-only"
    $driverFolder = Split-Path -Parent $driverGame
    Assert ((Invoke-Patcher @("--in-place", $driverGame, $Resolution)) -eq 0) "driver-only install succeeds"
    Assert (Test-Path -LiteralPath (Join-Path $driverFolder "dinput8.dll")) "driver compatibility installs its loader"
    Assert (Test-Path -LiteralPath (Join-Path $driverFolder "k1-modern-driver-compatibility.asi")) "driver compatibility installs its payload"
    Assert (-not (Test-Path -LiteralPath (Join-Path $driverFolder "patches\kmrp-controller.dll"))) "KMRP Controller's module is not installed"
    Assert-Config $driverFolder @("kmrp", "kmrp-movies", "kmrp-map-notes") $cleanHash "without the controller: KMRP, Movies and Map Notes"
    Assert ((Invoke-Patcher @("--restore", $driverGame)) -eq 0) "driver-only restore succeeds"
    Assert (-not (Test-Path -LiteralPath (Join-Path $driverFolder "k1-modern-driver-compatibility.asi"))) "restore removes driver compatibility"
    Assert (-not (Test-Path -LiteralPath (Join-Path $driverFolder "dinput8.dll"))) "restore removes its loader"

    Write-Host "Case 5b every option off: KMRP and KMRP Movies still install"
    Set-TestOptions $false $false $false
    $bareGame = New-Install "no-options"
    $bareFolder = Split-Path -Parent $bareGame
    Assert ((Invoke-Patcher @("--in-place", $bareGame, $Resolution)) -eq 0) "install with every option off succeeds"
    Assert (-not (Test-Path -LiteralPath (Join-Path $bareFolder "dinput8.dll"))) "no ASI loader"
    Assert-Config $bareFolder @("kmrp", "kmrp-movies") $cleanHash "KMRP and KMRP Movies alone"
    Assert ((Invoke-Patcher @("--restore", $bareGame)) -eq 0) "restore succeeds"
    Assert ((Get-Sha $bareGame) -eq $cleanHash) "swkotor.exe is the original"

    # Switching an option on an installed game rewrites the config both ways, with no
    # stale module left from the other set.
    Write-Host "Case 5c switching the controller option on an installed game"
    Set-TestOptions $false $true $true
    $switchGame = New-Install "switch-option"
    $switchFolder = Split-Path -Parent $switchGame
    Assert ((Invoke-Patcher @("--in-place", $switchGame, $Resolution)) -eq 0) "install with the controller on"
    Assert-Config $switchFolder $allIds $cleanHash "the controller is installed"
    Set-TestOptions $false $true $false
    Assert ((Invoke-Patcher @("--in-place", $switchGame, $Resolution)) -eq 0) "reinstall with the controller off"
    Assert-Config $switchFolder @("kmrp", "kmrp-movies", "kmrp-map-notes") $cleanHash "switching off leaves no KMRP Controller"
    Assert (-not (Test-Path -LiteralPath (Join-Path $switchFolder "patches\kmrp-controller.dll"))) "and no stale module"
    Assert ((Get-Sha $switchGame) -eq $laaHash) "the reinstall set the large-address flag again, once"
    Set-TestOptions $false $true $true
    Assert ((Invoke-Patcher @("--in-place", $switchGame, $Resolution)) -eq 0) "reinstall with the controller on again"
    Assert-Config $switchFolder $allIds $cleanHash "switching back on restores KMRP Controller"
    Assert ((Invoke-Patcher @("--restore", $switchGame)) -eq 0) "switched fixture restores"
    Assert ((Get-Sha $switchGame) -eq $cleanHash) "swkotor.exe is the original"
    Assert ((Get-Sha (Join-Path $switchFolder "binkw32.dll")) -eq $standInHash) "binkw32.dll is the game's"

    # All three optional components default on since 2026-09-24, so a first run with no
    # saved settings must install all of them. The finally block puts the real
    # settings.json back.
    Write-Host "Case 6  the defaults, with no saved settings"
    if (Test-Path -LiteralPath $settingsPath) { Remove-Item -LiteralPath $settingsPath -Force }
    $defaultGame = New-Install "defaults"
    $defaultFolder = Split-Path -Parent $defaultGame
    Assert ((Invoke-Patcher @("--in-place", $defaultGame, $Resolution)) -eq 0) "default install succeeds"
    Assert (Test-Path -LiteralPath (Join-Path $defaultFolder "k1-modern-driver-compatibility.asi")) "driver compatibility is on by default"
    Assert-Config $defaultFolder $allIds $cleanHash "controller support and the marker fixes are on by default"
    Assert ((Invoke-Patcher @("--restore", $defaultGame)) -eq 0) "default install restores"

    # kmrp-controller.ini is the player's to edit (rumble mode, strength, debug
    # log). An edited copy must never block an install, never be overwritten,
    # and never be deleted by restore -- the opposite of every other file here.
    Write-Host "Case 7  edited controller settings survive restore and reinstall"
    Set-TestOptions $true $true $true
    $tunedGame = New-Install "tuned-settings"
    $tunedFolder = Split-Path -Parent $tunedGame
    $tunedIni = Join-Path $tunedFolder "kmrp-controller.ini"
    Assert ((Invoke-Patcher @("--in-place", $tunedGame, $Resolution)) -eq 0) "settings fixture installs"
    Assert ([IO.File]::ReadAllText($tunedIni).Contains("Mode=Enhanced")) "the installed settings default to Enhanced"
    $tuned = "[Rumble]`r`nMode=Original`r`nStrength=40`r`nDebug=0`r`n"
    [IO.File]::WriteAllText($tunedIni, $tuned, [Text.UTF8Encoding]::new($false))
    Assert ((Invoke-Patcher @("--restore", $tunedGame)) -eq 0) "restore with edited settings succeeds"
    Assert ([IO.File]::ReadAllText($tunedIni) -eq $tuned) "restore keeps edited settings"
    Assert (-not (Test-Path -LiteralPath (Join-Path $tunedFolder "patches\kmrp.dll"))) "restore still removes the modules"
    Assert ((Invoke-Patcher @("--in-place", $tunedGame, $Resolution)) -eq 0) "reinstall over edited settings succeeds"
    Assert ([IO.File]::ReadAllText($tunedIni) -eq $tuned) "reinstall keeps edited settings"
    Assert (-not ([IO.File]::ReadAllText((Join-Path $tunedFolder "KMRP_KPM.manifest")).Contains("kmrp-controller.ini"))) "edited settings are not claimed by the manifest"
    Assert ((Invoke-Patcher @("--restore", $tunedGame)) -eq 0) "second restore succeeds"
    Assert ([IO.File]::ReadAllText($tunedIni) -eq $tuned) "second restore keeps edited settings"

    Write-Host "Case 8  the large-address flag already set: left alone both ways"
    $laaSource = Join-Path $WorkRoot "pre-laa-source.exe"
    Copy-Item -LiteralPath $CleanExe -Destination $laaSource
    $stream = [IO.File]::Open($laaSource, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite)
    try { $stream.Position = 0x926; $stream.WriteByte(0x2F); $stream.WriteByte(0x01) } finally { $stream.Dispose() }
    Assert ((Get-Sha $laaSource) -eq $laaHash) "the fixture is the known large-address executable"
    $laaGame = New-Install "pre-laa" $laaSource
    Assert ((Invoke-Patcher @("--in-place", $laaGame, $Resolution)) -eq 0) "install over it succeeds"
    Assert (-not ([IO.File]::ReadAllText((Join-Path (Split-Path -Parent $laaGame) "KMRP_KPM.manifest")) -match "(?m)^laa\t")) "the flag is not claimed"
    Assert ((Invoke-Patcher @("--restore", $laaGame)) -eq 0) "restore succeeds"
    Assert ((Get-Sha $laaGame) -eq $laaHash) "restore leaves the player's flag set"

    Write-Host "Case 9  Steam's swkotor.exe"
    if (-not $SteamExe) {
        Write-Host "  SKIPPED  no build-inputs\swkotor-steam.exe; the Steam case did not run" -ForegroundColor DarkYellow
    } elseif ((Get-Sha $SteamExe) -ne $steamHash) {
        Assert $false "build-inputs\swkotor-steam.exe is Steam's unmodified swkotor.exe"
    } else {
        $steamGame = New-Install "steam" $SteamExe
        $steamFolder = Split-Path -Parent $steamGame
        Assert ((Invoke-Patcher @("--in-place", $steamGame, $Resolution)) -eq 0) "the install succeeds over Steam's executable"
        Assert ((Get-Sha $steamGame) -eq $steamHash) "Steam's executable is byte-for-byte unmodified"
        Assert-Config $steamFolder $allIds $steamHash "patch_config.toml names Steam's executable, with the same four patches"
        Assert ((Get-Sha (Join-Path $steamFolder "binkw32.dll")) -eq $proxyHash) "the proxy is installed"
        Assert (-not ([IO.File]::ReadAllText((Join-Path $steamFolder "KMRP_KPM.manifest")) -match "(?m)^laa\t")) "no large-address flag is recorded"
        # KPM knows Steam's unchanged executable by its hash, but its releases after 0.7.1
        # read the deployment from this file, and on Steam only the proxy works.
        $steamState = [IO.File]::ReadAllText((Join-Path $steamFolder "kpm_install_state.json")) | ConvertFrom-Json
        Assert ($steamState.OriginalHash -eq $steamHash -and $steamState.OriginalFileSize -eq 4395008 -and
                $steamState.OriginalVersion.Distribution -eq 1 -and $steamState.OriginalVersion.Hash -eq $steamHash) "kpm_install_state.json names Steam's executable"
        Assert ($steamState.LibraryProxyInstalled -eq $true) "and records the proxy, which KPM's Apply then keeps"
        Assert (@(Get-ChildItem -LiteralPath $steamFolder -Filter "*.backup.*").Count -eq 0) "no KPM backup: the executable is not changed"
        Assert ((Invoke-Patcher @("--restore", $steamGame)) -eq 0) "restore succeeds"
        Assert ((Get-Sha $steamGame) -eq $steamHash) "Steam's executable is still unmodified"
        Assert ((Get-Sha (Join-Path $steamFolder "binkw32.dll")) -eq $standInHash) "the game's binkw32.dll is back"
        Assert (-not (Test-Path -LiteralPath (Join-Path $steamFolder "KotorPatcher.dll"))) "the runtime is removed"
        Assert (-not (Test-Path -LiteralPath (Join-Path $steamFolder "kpm_install_state.json"))) "and kpm_install_state.json"
    }
}
finally {
    Restore-KpmLauncherSettings $kpmLauncherSettings
    if ((Test-Path -LiteralPath $errorLog) -and -not $errorLogBefore) { Remove-Item -LiteralPath $errorLog -Force }
    if ($settingsExisted) { Copy-Item -LiteralPath $settingsCopy -Destination $settingsPath -Force }
    elseif (Test-Path -LiteralPath $settingsPath) { Remove-Item -LiteralPath $settingsPath -Force }
    Restore-TestNvidiaProfiles $WorkRoot
    # Kept fixtures keep their DPI values; --restore on each removes them.
    if (-not $KeepWorkRoot) { Remove-TestDpiValues $WorkRoot }

    if (-not $KeepWorkRoot -and (Test-Path -LiteralPath $WorkRoot)) {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $WorkRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a test directory outside the system temp root: $WorkRoot"
        }
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
}

if ($script:Failures -ne 0) { throw "$($script:Failures) installer regression check(s) failed." }
Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
