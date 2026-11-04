<#
.SYNOPSIS
    Regression test for what KMRP's installer puts in a game folder since 2026-10-04:
    KOTOR Patch Manager's runtime with KMRP's patch, "kmrp", its options, and
    (since 2026-10-05) the controller patch, "kmrp-controller", beside it.

.DESCRIPTION
    Runs the built installer from the command line on throwaway game folders (the
    editable 1.03 executable from build-inputs, a stand-in binkw32.dll and a small
    swkotor.ini) and checks:

      1. every option on: patch_config.toml holds the one patch with every hook the
         .kpatch has, configs\kmrp.ini says controller and map-notes are on and
         debug-logs is off, keeping a section of its own that was there before, the
         module under patches\ is the one inside KMRP.kpatch, nothing is written to
         Override, no data file and no resolution list, and swkotor.ini holds the
         size asked for;
      2. controller support and map notes off: only the hooks without a condition
         are written, and configs\kmrp.ini says both are off;
      3. a resolution choice left in the settings by a build before 2026-10-07:
         no kmrp-resolutions.txt is written, the choice is gone;
      4. Restore Original: the folder is as it was, file for file;
      5. the .kpatch delivered to KOTOR Patch Manager's patch folder passes
         tools\build_native_kpatch.py --check;
      6. High FPS Fix on (off by default, and absent from every case above): D3M0's
         High FPS Fixes is the third patch in patch_config.toml with its 36 hooks,
         its module and its .kpatch are the bundled file's, and restore removes them.

    Case 8 (2026-10-19, rewritten 2026-10-31 for issue 44): Modern Driver Compatibility
    on, off in every case above, over an older KMRP's standalone K1DC: the two old files
    and their manifest are gone, Synchro's patch is the third in patch_config.toml with
    its 28 hooks and their parameters, its module and its .kpatch are the bundled file's,
    and Restore Original removes all of it.
    Case 9 (2026-10-19, rewritten 2026-10-31): the same on a PC that lacks a function the
    module imports (Windows 7, faked with KMRP_TEST_MISSING_IMPORT): the install writes
    the vendored Windows 7 and 8 build's two files beside the game with their manifest and
    no .kpatch, and Restore Original removes them. (Until 2026-10-31 case 8 checked the
    2.0.0 standalone files and case 9 that neither was written.)
    Case 10 (2026-10-19): Marked Empty Containers on, off in every case above (its default
    is on): ShaeMyName's patch is the third in patch_config.toml with its one hook and no
    DLL, nothing of it goes into patches\, its .kpatch is the bundled file, and Restore
    Original removes all of it.

    Cases 13 to 17 (2026-11-01, audit INS-02 to INS-04): KPM taking the runtime over and
    KMRP installing over that; a manifest without ini rows; an install failing near its
    end, its rollback succeeding and its rollback blocked by a held file; and the
    installer killed at fifteen moments, each followed by an install and a restore. Which
    stage a kill lands on varies from run to run, and the log says.

    Cases 18 to 21 (2026-11-01, audit INS-05 to INS-09): a damaged manifest; a restore
    that cannot put everything back; the status against the files (the installer's
    test-only --needs-repair); and the guards, with swkotor.exe held open as a running
    program's file is, a second installer started beside the first, and a folder this
    account is denied by an ACL. The last two read KMRP.startup-error.log, which the
    installer writes beside itself when the command line fails.

    Case 11 (2026-10-20): an install over one made before 2026-10-20, whose files were
    loose in the game folder (its manifests, settings, KPM's licence, the swkotor.ini
    backup, KMRP.log): afterwards none is left there, the manifest names the settings in
    KMRP's folder, the old log is KMRP\logs\install.log with its lines first, and Restore
    Original leaves the folder as it was. Since the same day case 1 checks that KMRP's own
    files are in its folder, KMRP, and none is loose beside the game, and every restore
    is compared without KMRP\backups and KMRP\logs, which it keeps on purpose.
    Since 2026-10-19 case 1 also checks the art pack, patches\kmrp-assets.pack, the
    build's own, and the art the installer makes from it before the game starts: the
    common files and at least one size in the cache. Case 4 checks that Restore
    Original removes both. The cache is the module's, under %LOCALAPPDATA%, which the
    run points at a folder of its own, so the player's own cache is never touched.

    The installer reads its options from %LOCALAPPDATA%\KMRP\settings.json and
    KOTOR Patch Manager's patch folder from %APPDATA%\KPatchLauncher\settings.json.
    Both are replaced for the run and put back in a finally block, from copies kept
    on disk, so a stopped run can be repaired by hand from the work folder.

    It does not start the game. See docs\kpm-edition.md, "One patch since 2026-10-04".

.EXAMPLE
    .\testing\regression\Test-InstallerPatch.ps1
#>
[CmdletBinding()]
param(
    [string]$Installer,
    [string]$SourceExe,
    [string]$WorkRoot
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Installer) { $Installer = & (Join-Path $projectRoot "tools\kmrp_version.ps1") -WindowsInstaller }
if (-not $SourceExe) { $SourceExe = Join-Path $projectRoot "build-inputs\swkotornopatch.exe" }
if (-not $WorkRoot) { $WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("kmrp-installer-patch-" + [Guid]::NewGuid().ToString("N")) }
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
foreach ($needed in @($Installer, $SourceExe)) {
    if (-not (Test-Path -LiteralPath $needed)) { throw "Missing: $needed" }
}

$script:failures = 0
function Assert([bool]$condition, [string]$what) {
    if ($condition) { Write-Host "  PASS  $what" }
    else { Write-Host "  FAIL  $what" -ForegroundColor Red; $script:failures++ }
}
function Get-Sha([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
function Invoke-Installer([string[]]$arguments) {
    $process = Start-Process -FilePath $Installer -ArgumentList $arguments -Wait -PassThru
    return $process.ExitCode
}
# Why the installer last stopped, which it writes beside itself.
function Get-InstallerError {
    $log = Join-Path (Split-Path -Parent $Installer) "KMRP.startup-error.log"
    if (Test-Path -LiteralPath $log) { return ([IO.File]::ReadAllLines($log) | Select-Object -First 1) }
    return "no error log"
}
function New-Fixture([string]$name) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    Copy-Item -LiteralPath $SourceExe -Destination (Join-Path $folder "swkotor.exe")
    [IO.File]::WriteAllBytes((Join-Path $folder "binkw32.dll"), [byte[]](1..64))
    [IO.File]::WriteAllText((Join-Path $folder "swkotor.ini"),
        "[Graphics Options]`r`nFullScreen=1`r`nWidth=800`r`nHeight=600`r`n", [Text.UTF8Encoding]::new($false))
    return (Join-Path $folder "swkotor.exe")
}
# What Restore Original keeps on purpose: the swkotor.ini backup and the install log, in
# KMRP\backups and KMRP\logs since 2026-10-20 (KmrpFolder in src\patcher\KmrpPatcher.cs),
# and the backup beside swkotor.ini before that.
$kept = 'swkotor\.ini\.kotor-ui-backup|^\\KMRP\\(backups|logs)\\'
function Get-Listing([string]$folder) {
    Get-ChildItem -LiteralPath $folder -Recurse -File | Sort-Object FullName | ForEach-Object {
        $_.FullName.Substring($folder.Length) + " " + (Get-Sha $_.FullName)
    }
}
function Set-KmrpSettings([bool]$controller, [bool]$markers, [string]$off = "", [string]$extra = "", [bool]$highFps = $false,
                          [bool]$driverCompat = $false, [bool]$emptyContainers = $false) {
    $text = "{`r`n  `"driverCompatibility`": " + $driverCompat.ToString().ToLowerInvariant() +
        ",`r`n  `"markerFixes`": " + $markers.ToString().ToLowerInvariant() +
        ",`r`n  `"controllerSupport`": " + $controller.ToString().ToLowerInvariant()
    if ($off) { $text += ",`r`n  `"resolutionsOff`": `"$off`"" }
    if ($extra) { $text += ",`r`n  `"resolutionsExtra`": `"$extra`"" }
    # Always written: left out, High FPS Fix follows this PC's display (on above 60 Hz),
    # and the cases would differ from one test machine to the next.
    $text += ",`r`n  `"highFpsFix`": " + $highFps.ToString().ToLowerInvariant()
    # Always written too: left out, Marked Empty Containers is on, its default since
    # 2026-10-19. The cases before it were written without it; case 10 turns it on.
    $text += ",`r`n  `"markedEmptyContainers`": " + $emptyContainers.ToString().ToLowerInvariant()
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $kmrpSettings) | Out-Null
    [IO.File]::WriteAllText($kmrpSettings, $text + "`r`n}`r`n", [Text.UTF8Encoding]::new($false))
}
function Get-Config([string]$folder) {
    $text = [IO.File]::ReadAllText((Join-Path $folder "patch_config.toml"))
    return [pscustomobject]@{
        Text = $text
        Ids = @([regex]::Matches($text, '(?m)^id = "([^"]+)"') | ForEach-Object { $_.Groups[1].Value })
        Hooks = [regex]::Matches($text, '(?m)^\[\[patches\.hooks\]\]').Count
    }
}
# The [Patch Options] section of configs\kmrp.ini: the values the patch was installed with.
function Get-Options([string]$folder) {
    $path = Join-Path $folder "configs\kmrp.ini"
    $text = if (Test-Path -LiteralPath $path) { [IO.File]::ReadAllText($path) } else { "" }
    $section = [regex]::Match($text, '(?s)\[Patch Options\]\r?\n(.*?)(?=\r?\n\[|\z)').Groups[1].Value
    return [pscustomobject]@{
        Text = $text
        Controller = [regex]::Match($section, '(?m)^controller=([01])').Groups[1].Value   # gone since 2026-10-05: must be empty
        MapNotes = [regex]::Match($section, '(?m)^map-notes=([01])').Groups[1].Value
        HdIcons = [regex]::Match($section, '(?m)^hd-icons=([01])').Groups[1].Value
        DebugLogs = [regex]::Match($section, '(?m)^debug-logs=([01])').Groups[1].Value
    }
}

$kmrpSettings = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "KMRP\settings.json"
$kpmSettings = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData)) "KPatchLauncher\settings.json"
$kmrpCopy = Join-Path $WorkRoot "player-kmrp-settings.json"
$kpmCopy = Join-Path $WorkRoot "player-kpm-settings.json"
$hadKmrp = Test-Path -LiteralPath $kmrpSettings
$hadKpm = Test-Path -LiteralPath $kpmSettings
if ($hadKmrp) { Copy-Item -LiteralPath $kmrpSettings -Destination $kmrpCopy }
if ($hadKpm) { Copy-Item -LiteralPath $kpmSettings -Destination $kpmCopy }
$kpmPatches = Join-Path $WorkRoot "kpm-patch-folder"
New-Item -ItemType Directory -Force -Path $kpmPatches | Out-Null
# The art cache the installer makes (ArtPreparation, KpmEdition.cs), in this run's folder:
# the installer and the module it loads take %LOCALAPPDATA% from the environment.
$playerLocalAppData = $env:LOCALAPPDATA
$testLocalAppData = Join-Path $WorkRoot "localappdata"
New-Item -ItemType Directory -Force -Path $testLocalAppData | Out-Null
$artCache = Join-Path $testLocalAppData "KMRP\cache"
$buildPack = Join-Path $projectRoot "build\native-runtime\kmrp-assets.pack"

try {
    $env:LOCALAPPDATA = $testLocalAppData
    # KOTOR Patch Manager's patch folder for the run: a folder of this test's own.
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $kpmSettings) | Out-Null
    [IO.File]::WriteAllText($kpmSettings, "{`r`n  `"GamePath`": `"`",`r`n  `"PatchesPath`": `"" +
        ($kpmPatches -replace '\\', '\\') + "`",`r`n  `"CheckedPatchIds`": []`r`n}", [Text.UTF8Encoding]::new($false))

    Write-Host "Case 1  every option on"
    Set-KmrpSettings $true $true
    $game = New-Fixture "all-on"
    $folder = Split-Path -Parent $game
    # A settings file the patch already has, with a section that is not the installer's.
    New-Item -ItemType Directory -Force -Path (Join-Path $folder "configs") | Out-Null
    [IO.File]::WriteAllText((Join-Path $folder "configs\kmrp.ini"), "[Mine]`r`nkept=1`r`n", [Text.UTF8Encoding]::new($false))
    $before = Get-Listing $folder
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $config = Get-Config $folder
    Assert (($config.Ids -join ",") -eq "kmrp,kmrp-controller") "patch_config.toml holds KMRP's patch and the controller patch, in that order"
    $options = Get-Options $folder
    Assert ($options.Controller -eq "" -and $options.MapNotes -eq "1") "configs\kmrp.ini says map-notes is on, and has no controller option"
    Assert ($options.HdIcons -eq "1") "configs\kmrp.ini says hd-icons is on"
    $controllerIni = Join-Path $folder "configs\kmrp-controller.ini"
    Assert ((Test-Path -LiteralPath $controllerIni) -and ([IO.File]::ReadAllText($controllerIni) -match '(?m)^debug-logs=0') -and
        -not ([IO.File]::ReadAllText($controllerIni) -match '(?m)^xbox-hud=')) "configs\kmrp-controller.ini has debug-logs off and leaves the Xbox-style HUD to the player's own setting"
    Assert ($options.DebugLogs -eq "0") "debug logs are off"
    Assert ($options.Text -match '(?m)^\[Mine\]\r?\nkept=1') "the section that was already in the file is kept"
    Assert (-not ($options.Text -match '(?m)^movies=')) "the movie fixes are not an option"
    Assert (-not ($config.Text -match 'patches\.options')) "patch_config.toml has no options table"
    $kpatch = Join-Path $kpmPatches "KMRP.kpatch"
    Assert (Test-Path -LiteralPath $kpatch) "KMRP.kpatch is in KOTOR Patch Manager's patch folder"
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($kpatch)
    try {
        $hooksText = (New-Object IO.StreamReader ($zip.GetEntry("kotor1.hooks.toml").Open())).ReadToEnd()
        $moduleStream = $zip.GetEntry("binaries/windows_x86.dll").Open()
        $sha = [Security.Cryptography.SHA256]::Create()
        $moduleHash = [BitConverter]::ToString($sha.ComputeHash($moduleStream)).Replace("-", "")
        $moduleStream.Dispose()
    } finally { $zip.Dispose() }
    $allHooks = [regex]::Matches($hooksText, '(?m)^\[\[hooks\]\]').Count
    $conditional = [regex]::Matches($hooksText, '(?m)^when = ').Count
    # The controller patch, delivered beside it and installed with it.
    $controllerKpatch = Join-Path $kpmPatches "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch"
    Assert (Test-Path -LiteralPath $controllerKpatch) "the controller patch's .kpatch is in KOTOR Patch Manager's patch folder too"
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($python) {
        & $python (Join-Path $projectRoot "tools\build_controller_kpatch.py") --check $controllerKpatch | Out-Null
        Assert ($LASTEXITCODE -eq 0) "tools\build_controller_kpatch.py --check accepts the delivered controller patch"
    }
    $zip = [IO.Compression.ZipFile]::OpenRead($controllerKpatch)
    try {
        $controllerHooks = [regex]::Matches((New-Object IO.StreamReader ($zip.GetEntry("kotor1.hooks.toml").Open())).ReadToEnd(), '(?m)^\[\[hooks\]\]').Count
        $moduleStream = $zip.GetEntry("binaries/windows_x86.dll").Open()
        $sha = [Security.Cryptography.SHA256]::Create()
        $controllerModuleHash = [BitConverter]::ToString($sha.ComputeHash($moduleStream)).Replace("-", "")
        $moduleStream.Dispose()
    } finally { $zip.Dispose() }
    Assert ($conditional -eq 0) "no hook of KMRP's patch is an option's"
    Assert ($config.Hooks -eq ($allHooks + $controllerHooks)) "every hook of both patches is in the config ($allHooks + $controllerHooks)"
    Assert ((Get-Sha (Join-Path $folder "patches\kmrp.dll")) -eq $moduleHash) "patches\kmrp.dll is the module inside KMRP.kpatch"
    Assert ((Get-Sha (Join-Path $folder "patches\kmrp-controller.dll")) -eq $controllerModuleHash) "patches\kmrp-controller.dll is the module inside the controller patch"
    Assert (@(Get-ChildItem -LiteralPath (Join-Path $folder "patches")).Count -eq 3) "the patches folder holds those two modules and the art pack"
    $pack = Join-Path $folder "patches\kmrp-assets.pack"
    Assert ((Test-Path -LiteralPath $pack) -and (-not (Test-Path -LiteralPath $buildPack) -or
        (Get-Sha $pack) -eq (Get-Sha $buildPack))) "patches\kmrp-assets.pack is the build's art pack"
    $builds = @(Get-ChildItem -LiteralPath $artCache -Directory -ErrorAction SilentlyContinue)
    $made = if ($builds.Count -eq 1) { @(Get-ChildItem -LiteralPath (Join-Path $builds[0].FullName "sets") -Filter "*.complete" -File) } else { @() }
    Assert ($builds.Count -eq 1 -and (Test-Path -LiteralPath (Join-Path $builds[0].FullName "store.complete")) -and $made.Count -ge 1) "the art is made before the game starts: the common files and $($made.Count) sizes, in one build's cache"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "Override"))) "nothing is written to Override"
    foreach ($absent in @("kmrp-kpm.dat", "kmrp-sdl3.dll", "kmrp-resolutions.txt")) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder $absent))) "no $absent"
    }
    $ini = [IO.File]::ReadAllText((Join-Path $folder "swkotor.ini"))
    Assert ($ini -match '(?m)^Width=1920' -and $ini -match '(?m)^Height=1080') "swkotor.ini starts the game at the size asked for"
    Assert ($ini -match '(?m)^AllowHighMonitorFrequency=0' -and $ini -match '(?m)^RefreshRate=60' -and $ini -match '(?m)^V-Sync=1') "without High FPS Fix swkotor.ini holds the game at 60: no higher rates, RefreshRate=60, V-Sync on"
    Assert ((Test-Path -LiteralPath (Join-Path $folder "KotorPatcher.dll")) -and (Test-Path -LiteralPath (Join-Path $folder "binkw32Hooked.dll"))) "KOTOR Patch Manager's runtime and proxy are in place"
    # KMRP's own files in its folder since 2026-10-20, none loose beside the game.
    foreach ($name in @("KMRP\kpm.manifest", "KMRP\controller.ini", "KMRP\kotor-patch-manager-LICENSE.txt",
                        "KMRP\backups\swkotor.ini", "KMRP\backups\swkotor.ini.sha256")) {
        Assert (Test-Path -LiteralPath (Join-Path $folder $name)) "$name is in KMRP's folder"
    }
    $loose = @(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -match '^(KMRP|kmrp)[-_.]|\.kotor-ui-backup' })
    Assert ($loose.Count -eq 0) ("nothing of KMRP's is loose in the game folder" + $(if ($loose.Count) { ": " + ($loose.Name -join ", ") } else { "" }))

    Write-Host "Case 4  Restore Original"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"
    Assert (-not (Test-Path -LiteralPath $kpatch)) "the .kpatch this install created is removed"
    Assert (-not (Test-Path -LiteralPath $controllerKpatch)) "and the controller patch's"
    Assert (-not (Test-Path -LiteralPath $artCache)) "the art cache is removed"

    Write-Host "Case 2  controller support and map notes off"
    Set-KmrpSettings $false $false
    $game = New-Fixture "all-off"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $config = Get-Config $folder
    Assert (($config.Ids -join ",") -eq "kmrp") "without controller support the controller patch is not installed"
    Assert ($config.Hooks -eq $allHooks) "KMRP's hooks, the same as beside the controller patch ($allHooks)"
    Assert (-not (Test-Path -LiteralPath (Join-Path $kpmPatches "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch"))) "the controller patch's .kpatch is not delivered"
    Assert (@(Get-ChildItem -LiteralPath (Join-Path $folder "patches")).Count -eq 2) "the patches folder holds KMRP's module alone, and the art pack"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "configs\kmrp-controller.ini"))) "no options file for the controller patch"
    $options = Get-Options $folder
    Assert ($options.Controller -eq "" -and $options.MapNotes -eq "0") "configs\kmrp.ini says map-notes is off"

    Write-Host "Case 5  the delivered .kpatch"
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($python) {
        & $python (Join-Path $projectRoot "tools\build_native_kpatch.py") --check (Join-Path $kpmPatches "KMRP.kpatch") | Out-Null
        Assert ($LASTEXITCODE -eq 0) "tools\build_native_kpatch.py --check accepts it"
    } else { Write-Host "  SKIP  python is not on PATH" }
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "configs"))) "restore removes the configs folder it created"

    Write-Host "Case 3  a resolution choice left in the settings by an earlier build"
    Set-KmrpSettings $true $true "" "1000x700"
    $game = New-Fixture "resolutions"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $list = Join-Path $folder "kmrp-resolutions.txt"
    Assert (-not (Test-Path -LiteralPath $list)) "no kmrp-resolutions.txt is written"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"

    Write-Host "Case 6  High FPS Fix on"
    Set-KmrpSettings $true $true "" "" $true
    $game = New-Fixture "high-fps"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $config = Get-Config $folder
    Assert (($config.Ids -join ",") -eq "kmrp,kmrp-controller,high-fps-fixes") "patch_config.toml holds KMRP's patch, the controller patch and High FPS Fixes, in that order"
    $bundled = Join-Path $projectRoot "third_party\Included\HighFpsFixes-1.0.1 by D3M0\HighFpsFixes.kpatch"
    $zip = [IO.Compression.ZipFile]::OpenRead($bundled)
    try {
        $fpsHooks = [regex]::Matches((New-Object IO.StreamReader ($zip.GetEntry("kotor1.hooks.toml").Open())).ReadToEnd(), '(?m)^\[\[hooks\]\]').Count
        $moduleStream = $zip.GetEntry("binaries/windows_x86.dll").Open()
        $fpsModuleHash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($moduleStream)).Replace("-", "")
        $moduleStream.Dispose()
    } finally { $zip.Dispose() }
    Assert ($fpsHooks -eq 36 -and $config.Hooks -eq ($allHooks + $controllerHooks + $fpsHooks)) "every hook of the three patches is in the config ($allHooks + $controllerHooks + $fpsHooks)"
    $fpsModule = Join-Path $folder "patches\high-fps-fixes.dll"
    Assert ((Test-Path -LiteralPath $fpsModule) -and (Get-FileHash -LiteralPath $fpsModule -Algorithm SHA256).Hash -eq $fpsModuleHash) "patches\high-fps-fixes.dll is the module inside the bundled patch"
    $fpsKpatch = Join-Path $kpmPatches "HighFpsFixes.kpatch"
    Assert ((Test-Path -LiteralPath $fpsKpatch) -and (Get-FileHash -LiteralPath $fpsKpatch -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $bundled -Algorithm SHA256).Hash) "HighFpsFixes.kpatch in KOTOR Patch Manager's patch folder is the bundled file, unchanged"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "configs\high-fps-fixes.ini"))) "no options file for it: it has no options"
    $ini = [IO.File]::ReadAllText((Join-Path $folder "swkotor.ini"))
    $rate = [int][regex]::Match($ini, '(?m)^RefreshRate=(\d+)').Groups[1].Value
    Assert ($ini -match '(?m)^AllowHighMonitorFrequency=1' -and $rate -ge 60 -and $ini -notmatch '(?m)^V-Sync=') "with it swkotor.ini allows the higher rates, starts at the display's highest ($rate Hz here) and leaves V-Sync alone"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"
    Assert (-not (Test-Path -LiteralPath $fpsKpatch)) "the .kpatch this install created is removed"

    # An install over an install, which is what Upgrade does, follows the settings
    # chosen now: a patch turned off since is removed, one turned on is added
    # (the maintainer, 2026-10-19).
    Write-Host "Case 7  settings changed between two installs"
    Set-KmrpSettings $true $true "" "" $false
    $game = New-Fixture "changed"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    $controllerKpatch = Join-Path $kpmPatches "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the first install succeeds: controller support and map notes on, High FPS Fix off"
    $stamp = [IO.File]::ReadAllText((Join-Path $projectRoot "build\kmrp\build-stamp.txt")).Trim()
    Assert ([IO.File]::ReadAllText((Join-Path $folder "KMRP\kpm.manifest")) -match ('(?m)^built\t' + [regex]::Escape($stamp) + '\r?$')) "the manifest records this build's date ($stamp)"
    Assert (((Get-Config $folder).Ids -join ",") -eq "kmrp,kmrp-controller") "KMRP's patch and the controller patch"

    Set-KmrpSettings $false $false "" "" $true
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the second install succeeds: controller support and map notes off, High FPS Fix on"
    Assert (((Get-Config $folder).Ids -join ",") -eq "kmrp,high-fps-fixes") "patch_config.toml holds KMRP's patch and High FPS Fixes: the controller patch is gone"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "patches\kmrp-controller.dll"))) "the controller patch's module is removed"
    Assert (-not (Test-Path -LiteralPath $controllerKpatch)) "and its .kpatch from KOTOR Patch Manager's folder"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "configs\kmrp-controller.ini"))) "and its options file"
    Assert (Test-Path -LiteralPath (Join-Path $folder "patches\high-fps-fixes.dll")) "High FPS Fixes' module is added"
    Assert ((Get-Options $folder).MapNotes -eq "0") "configs\kmrp.ini says map-notes is off"

    Set-KmrpSettings $true $true "" "" $false
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the third install succeeds: the first settings again"
    Assert (((Get-Config $folder).Ids -join ",") -eq "kmrp,kmrp-controller") "patch_config.toml holds KMRP's patch and the controller patch again"
    Assert (Test-Path -LiteralPath (Join-Path $folder "patches\kmrp-controller.dll")) "the controller patch's module is back"
    Assert (Test-Path -LiteralPath $controllerKpatch) "and its .kpatch"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "patches\high-fps-fixes.dll"))) "High FPS Fixes' module is removed"
    Assert (-not (Test-Path -LiteralPath (Join-Path $kpmPatches "HighFpsFixes.kpatch"))) "and its .kpatch"
    Assert ((Get-Options $folder).MapNotes -eq "1") "configs\kmrp.ini says map-notes is on"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"

    Write-Host "Case 8  Modern Driver Compatibility on"
    Set-KmrpSettings $true $true "" "" $false $true
    $game = New-Fixture "driver-compat"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    # An older KMRP's standalone K1DC, as it left one: the two files beside the game and
    # their manifest. The install takes them out and puts the .kpatch in (issue 44).
    $oldFiles = @{ "dinput8.dll" = [byte[]](65..96); "k1-modern-driver-compatibility.asi" = [byte[]](97..122) }
    $oldManifest = "version`t2.0.0`r`n"
    foreach ($name in $oldFiles.Keys) {
        [IO.File]::WriteAllBytes((Join-Path $folder $name), $oldFiles[$name])
        $oldManifest += $name + "`t" + (Get-Sha (Join-Path $folder $name)) + "`r`n"
    }
    New-Item -ItemType Directory -Force -Path (Join-Path $folder "KMRP") | Out-Null
    [IO.File]::WriteAllText((Join-Path $folder "KMRP\driver-compat.manifest"), $oldManifest, [Text.UTF8Encoding]::new($false))
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    foreach ($name in @("dinput8.dll", "k1-modern-driver-compatibility.asi", "KMRP\driver-compat.manifest")) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) "the older standalone $name is gone"
    }
    $config = Get-Config $folder
    Assert (($config.Ids -join ",") -eq "kmrp,kmrp-controller,k1-modern-driver-compatibility") "patch_config.toml holds KMRP's patch, the controller patch and K1 Modern Driver Compatibility, in that order"
    $bundled = Join-Path $projectRoot "third_party\Included\k1-modern-driver-compatibility-2.0.1 by Synchro\k1-modern-driver-compatibility.kpatch"
    $zip = [IO.Compression.ZipFile]::OpenRead($bundled)
    try {
        $dcHooks = [regex]::Matches((New-Object IO.StreamReader ($zip.GetEntry("kotor1.hooks.toml").Open())).ReadToEnd(), '(?m)^\[\[hooks\]\]').Count
        $moduleStream = $zip.GetEntry("binaries/windows_x86.dll").Open()
        $dcModuleHash = [BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash($moduleStream)).Replace("-", "")
        $moduleStream.Dispose()
    } finally { $zip.Dispose() }
    Assert ($dcHooks -eq 28 -and $config.Hooks -eq ($allHooks + $controllerHooks + $dcHooks)) "every hook of the three patches is in the config ($allHooks + $controllerHooks + $dcHooks)"
    $section = [regex]::Match($config.Text, '(?s)id = "k1-modern-driver-compatibility"\r?\ndll = "([^"]*)"\r?\n(.*)$')
    Assert ($section.Success -and ([regex]::Matches($section.Groups[2].Value, '(?m)^\[\[patches\.hooks\.parameters\]\]').Count -ge 1)) "its hook parameters are in the config ([[patches.hooks.parameters]])"
    $dcModule = Join-Path $folder "patches\k1-modern-driver-compatibility.dll"
    Assert ((Test-Path -LiteralPath $dcModule) -and (Get-Sha $dcModule) -eq $dcModuleHash) "patches\k1-modern-driver-compatibility.dll is the module inside the bundled patch"
    $dcKpatch = Join-Path $kpmPatches "k1-modern-driver-compatibility.kpatch"
    Assert ((Test-Path -LiteralPath $dcKpatch) -and (Get-Sha $dcKpatch) -eq (Get-Sha $bundled)) "k1-modern-driver-compatibility.kpatch in KOTOR Patch Manager's patch folder is the bundled file, unchanged"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was before the older KMRP, file for file"
    Assert (-not (Test-Path -LiteralPath $dcKpatch)) "the .kpatch this install created is removed"

    Write-Host "Case 9  Modern Driver Compatibility on, on a PC that cannot run its .kpatch"
    # KMRP_TEST_MISSING_IMPORT counts one of the functions K1DC's module imports as
    # missing, the answer Windows 7 gives (DriverCompatOperations.MissingImport).
    # Start-Process passes the variable to the installer. Since 2026-10-31 such a PC gets
    # its author's build for Windows 7 and 8 beside the game; until then, no K1DC.
    Set-KmrpSettings $true $true "" "" $false $true
    $game = New-Fixture "driver-compat-windows7"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    $env:KMRP_TEST_MISSING_IMPORT = "WaitOnAddress"
    try { Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds" }
    finally { Remove-Item Env:KMRP_TEST_MISSING_IMPORT -ErrorAction SilentlyContinue }
    $vendored = Join-Path $projectRoot "third_party\Included\k1-modern-driver-compatibility-2.0.1 by Synchro\standalone-win7"
    foreach ($name in @("dinput8.dll", "k1-modern-driver-compatibility.asi")) {
        $installed = Join-Path $folder $name
        Assert ((Test-Path -LiteralPath $installed) -and (Get-Sha $installed) -eq (Get-Sha (Join-Path $vendored $name))) "$name is the vendored Windows 7 and 8 build's file"
    }
    $manifest = Join-Path $folder "KMRP\driver-compat.manifest"
    Assert ((Test-Path -LiteralPath $manifest) -and ([IO.File]::ReadAllText($manifest) -match '(?m)^version\t2\.0\.1-win7\r?$')) "KMRP\driver-compat.manifest records version 2.0.1-win7"
    Assert (((Get-Config $folder).Ids -join ",") -eq "kmrp,kmrp-controller") "KMRP's patch and the controller patch, without K1DC's .kpatch"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "patches\k1-modern-driver-compatibility.dll"))) "no K1DC module in patches\"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file: both files and the manifest are gone"

    Write-Host "Case 10 Marked Empty Containers on"
    Set-KmrpSettings $true $true "" "" $false $false $true
    $game = New-Fixture "empty-containers"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $config = Get-Config $folder
    Assert (($config.Ids -join ",") -eq "kmrp,kmrp-controller,k1-marked-empty-containers") "patch_config.toml holds KMRP's patch, the controller patch and Marked Empty Containers, in that order"
    $section = [regex]::Match($config.Text, '(?s)id = "k1-marked-empty-containers"\r?\ndll = "([^"]*)"\r?\n(.*)$')
    Assert ($section.Success -and $section.Groups[1].Value -eq "") "its section names no DLL, as KOTOR Patch Manager writes a patch without a module"
    Assert ($section.Groups[2].Value -match '(?m)^address = 0x00685E69$' -and $config.Hooks -eq ($allHooks + $controllerHooks + 1)) "its one hook, at 0x00685E69, is in the config ($allHooks + $controllerHooks + 1)"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "patches\k1-marked-empty-containers.dll"))) "nothing of it in patches\"
    $bundled = Join-Path $projectRoot "third_party\Included\K1MarkedEmptyContainers-1.0.0 by ShaeMyName\K1MarkedEmptyContainers.kpatch"
    $emptyKpatch = Join-Path $kpmPatches "K1MarkedEmptyContainers.kpatch"
    Assert ((Test-Path -LiteralPath $emptyKpatch) -and (Get-Sha $emptyKpatch) -eq (Get-Sha $bundled)) "K1MarkedEmptyContainers.kpatch in KOTOR Patch Manager's patch folder is the bundled file, unchanged"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"
    Assert (-not (Test-Path -LiteralPath $emptyKpatch)) "the .kpatch this install created is removed"

    Write-Host "Case 11 an install over one made before 2026-10-20, whose files were loose in the game folder"
    Set-KmrpSettings $true $true
    $game = New-Fixture "loose-files"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the first install succeeds"
    # Put the files where a build before 2026-10-20 wrote them, with the manifest's rows
    # naming them there, and an install log of the time.
    $legacy = [ordered]@{
        "KMRP\kpm.manifest" = "KMRP_KPM.manifest"; "KMRP\dpi.manifest" = "KMRP_DPI.manifest"
        "KMRP\controller.ini" = "kmrp-controller.ini"
        "KMRP\kotor-patch-manager-LICENSE.txt" = "kmrp-kotor-patch-manager-LICENSE.txt"
        "KMRP\backups\swkotor.ini" = "swkotor.ini.kotor-ui-backup"
        "KMRP\backups\swkotor.ini.sha256" = "swkotor.ini.kotor-ui-backup.sha256"
    }
    foreach ($name in $legacy.Keys) {
        $from = Join-Path $folder $name
        if (Test-Path -LiteralPath $from) { Move-Item -LiteralPath $from -Destination (Join-Path $folder $legacy[$name]) }
    }
    $manifest = Join-Path $folder "KMRP_KPM.manifest"
    $rows = [IO.File]::ReadAllText($manifest).Replace("file`tKMRP\controller.ini`t", "file`tkmrp-controller.ini`t").
        Replace("file`tKMRP\kotor-patch-manager-LICENSE.txt`t", "file`tkmrp-kotor-patch-manager-LICENSE.txt`t")
    [IO.File]::WriteAllText($manifest, $rows, [Text.UTF8Encoding]::new($false))
    Remove-Item -LiteralPath (Join-Path $folder "KMRP") -Recurse -Force
    [IO.File]::WriteAllText((Join-Path $folder "KMRP.log"), "an earlier install's line`r`n", [Text.UTF8Encoding]::new($false))
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install over it succeeds"
    $loose = @(Get-ChildItem -LiteralPath $folder -File | Where-Object { $_.Name -match '^(KMRP|kmrp)[-_.]|\.kotor-ui-backup' })
    Assert ($loose.Count -eq 0) ("nothing of KMRP's is left loose in the game folder" + $(if ($loose.Count) { ": " + ($loose.Name -join ", ") } else { "" }))
    $rows = [IO.File]::ReadAllText((Join-Path $folder "KMRP\kpm.manifest"))
    Assert ($rows -match '(?m)^file\tKMRP\\controller\.ini\t' -and $rows -notmatch '(?m)^file\tkmrp-controller\.ini\t') "the manifest names the settings in KMRP's folder"
    $log = Join-Path $folder "KMRP\logs\install.log"
    Assert ((Test-Path -LiteralPath $log) -and [IO.File]::ReadAllText($log).StartsWith("an earlier install's line")) "the earlier install log is KMRP\logs\install.log, its lines first"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"

    Write-Host ""
    Write-Host "Case 12 swkotor.ini is the player's through an upgrade and a restore (audit INS-01)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "player-settings"
    $folder = Split-Path -Parent $game
    $iniPath = Join-Path $folder "swkotor.ini"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the first install succeeds"
    $ini = [IO.File]::ReadAllText($iniPath)
    # What playing changes: the game's own options, KMRP's sliders, the size chosen in Options.
    $ini = $ini.Replace("Width=1920", "Width=2560").Replace("Height=1080", "Height=1440").Replace("V-Sync=1", "V-Sync=0")
    $ini += "`r`n[Sound Options]`r`nMusic Volume=33`r`n[KMRP Text]`r`nIconSize=75`r`n[KMRP HUD Size]`r`nAll=60`r`n"
    [IO.File]::WriteAllText($iniPath, $ini, [Text.UTF8Encoding]::new($false))
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install over it succeeds"
    $ini = [IO.File]::ReadAllText($iniPath)
    Assert ($ini -match '(?m)^Music Volume=33') "the game's own option survives the upgrade"
    Assert ($ini -match '(?m)^IconSize=75' -and $ini -match '(?m)^All=60') "KMRP's sliders survive the upgrade"
    Assert ($ini -match '(?m)^Width=2560' -and $ini -match '(?m)^Height=1440') "the size chosen in the game survives the upgrade"
    Assert ($ini -match '(?m)^V-Sync=0') "V-Sync as the player set it survives the upgrade"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $ini = [IO.File]::ReadAllText($iniPath)
    Assert ($ini -match '(?m)^Music Volume=33') "the game's own option survives Restore Original"
    Assert ($ini -notmatch 'KMRP') "KMRP's sections go with it"
    Assert ($ini -match '(?m)^Width=800' -and $ini -match '(?m)^Height=600' -or $ini -match '(?m)^Width=2560') "the size is the original, or the one the player chose"
    # A later install takes its backup from the file as it is then.
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "a new install succeeds"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "and its restore"
    Assert ([IO.File]::ReadAllText($iniPath) -match '(?m)^Music Volume=33') "the backup was not the first install's"

    Write-Host "Case 13 KOTOR Patch Manager took the runtime over (audit INS-02)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "taken-over"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    # KPM's Apply with another patch ticked: its config, which is no longer KMRP's.
    $toml = Join-Path $folder "patch_config.toml"
    [IO.File]::AppendAllText($toml, "`n[[patches]]`nid = `"someone-elses-patch`"`n")
    $pack = Join-Path $folder "patches\kmrp-assets.pack"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "installing over the takeover is not refused by KMRP's own art pack"
    Assert (Test-Path -LiteralPath $pack) "the art pack is written again"
    Assert ((Get-Content -LiteralPath $toml -Raw) -match 'someone-elses-patch') "KPM's config is left alone"
    $manifest = Join-Path $folder "KMRP\kpm.manifest"
    Assert ((Test-Path -LiteralPath $manifest) -and (Get-Content -LiteralPath $manifest -Raw) -match 'kmrp-assets\.pack') "the art pack is recorded"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    Assert (-not (Test-Path -LiteralPath $pack)) "the restore removes the art pack"
    Assert (Test-Path -LiteralPath $toml) "and leaves KPM's runtime"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "a new install after that restore succeeds"

    Write-Host "Case 14 a manifest from before its ini rows puts every key back"
    Set-KmrpSettings $true $true
    $game = New-Fixture "no-ini-rows"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $manifest = Join-Path $folder "KMRP\kpm.manifest"
    [IO.File]::WriteAllLines($manifest, [string[]]([IO.File]::ReadAllLines($manifest) | Where-Object { $_ -notmatch "^ini`t" }))
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    Assert ([IO.File]::ReadAllText((Join-Path $folder "swkotor.ini")) -match '(?m)^Width=800') "the size KMRP set goes back"

    Write-Host "Case 15 an install that fails near its end is undone (audit INS-04)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "fails-late"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    # A folder where the art pack goes: the last write fails, after the proxy.
    $blocker = Join-Path $folder "patches\kmrp-assets.pack"
    New-Item -ItemType Directory -Force -Path $blocker | Out-Null
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -ne 0) "the install fails"
    Assert ([IO.File]::ReadAllBytes((Join-Path $folder "binkw32.dll")).Length -eq 64) "the game's binkw32.dll is back"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KMRP\kpm.manifest"))) "no manifest is left"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KotorPatcher.dll"))) "the runtime is gone"
    [IO.Directory]::Delete($blocker)
    [IO.Directory]::Delete((Join-Path $folder "patches"))
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($before -join "`n") -eq ($after -join "`n")) "the folder is as it was"

    Write-Host "Case 16 a rollback a file blocks says so and Restore Original finishes it (audit INS-04)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "rollback-blocked"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    $blocker = Join-Path $folder "patches\kmrp-assets.pack"
    New-Item -ItemType Directory -Force -Path $blocker | Out-Null
    $runtime = Join-Path $folder "KotorPatcher.dll"
    $process = Start-Process -FilePath $Installer -ArgumentList @("--in-place", "`"$game`"", "1920x1080") -PassThru
    $held = $null
    while (-not $process.HasExited -and $held -eq $null) {
        try { $held = [IO.File]::Open($runtime, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None) }
        catch { }
    }
    Assert ($held -ne $null) "the test got hold of the runtime while the install ran"
    $process.WaitForExit()
    if ($held -ne $null) { $held.Dispose() }
    Assert ($process.ExitCode -ne 0) "the install fails"
    $manifest = Join-Path $folder "KMRP\kpm.manifest"
    Assert (Test-Path -LiteralPath $manifest) "the manifest stays, as the rollback did not finish"
    Assert ((Test-Path -LiteralPath $manifest) -and (Get-Content -LiteralPath $manifest -Raw) -match '(?m)^incomplete') "and it says the install is incomplete"
    [IO.Directory]::Delete($blocker)
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "Restore Original finishes the job"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    Assert (($before -join "`n") -eq ($after -join "`n")) "the folder is as it was"

    Write-Host "Case 17 an install stopped at any moment can be taken out and done again (audit INS-03)"
    Set-KmrpSettings $true $true
    # Where the installer happens to be at each delay does not matter: what is left must
    # always be something the next run can deal with.
    foreach ($delay in 150, 200, 250, 275, 300, 325, 350, 375, 400, 450, 500, 600, 800, 1100, 1500) {
        $game = New-Fixture "killed-$delay"
        $folder = Split-Path -Parent $game
        $before = Get-Listing $folder
        $iniBefore = Get-Sha (Join-Path $folder "swkotor.ini")
        $process = Start-Process -FilePath $Installer -ArgumentList @("--in-place", "`"$game`"", "1920x1080") -PassThru
        Start-Sleep -Milliseconds $delay
        if (-not $process.HasExited) { $process.Kill() }
        $process.WaitForExit()
        $stage = if (Test-Path -LiteralPath (Join-Path $folder "binkw32Hooked.dll")) { "after the rename" }
                 elseif (Test-Path -LiteralPath (Join-Path $folder "KotorPatcher.dll")) { "with the runtime in" }
                 elseif (Test-Path -LiteralPath (Join-Path $folder "KMRP\kpm.manifest")) { "with the manifest only" }
                 else { "before any change" }
        Write-Host "    stopped after $delay ms, $stage"
        $code = Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")
        Assert ($code -eq 0) "$delay ms: the next install succeeds"
        if ($code -ne 0) { Write-Host "    $(Get-InstallerError)"; continue }
        Assert ((Get-Content -LiteralPath (Join-Path $folder "KMRP\kpm.manifest") -Raw) -notmatch '(?m)^incomplete') "$delay ms: and is complete"
        Assert (Test-Path -LiteralPath (Join-Path $folder "binkw32Hooked.dll")) "$delay ms: it used KMRP's own runtime, not KPM's"
        Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "$delay ms: the restore succeeds"
        $after = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
        Assert (($before -join "`n") -eq ($after -join "`n")) "$delay ms: the folder is as it was"
        Assert ((Get-Sha (Join-Path $folder "swkotor.ini")) -eq $iniBefore) "$delay ms: swkotor.ini is as it was"
    }

    Write-Host "Case 17b a stop between the swkotor.ini backup's hash and the backup"
    Set-KmrpSettings $true $true
    $game = New-Fixture "hash-without-backup"
    $folder = Split-Path -Parent $game
    New-Item -ItemType Directory -Force -Path (Join-Path $folder "KMRP\backups") | Out-Null
    [IO.File]::WriteAllText((Join-Path $folder "KMRP\backups\swkotor.ini.sha256"), ("0" * 64) + "`r`n")
    [IO.File]::WriteAllText((Join-Path $folder "KMRP\backups\swkotor.ini.kotor-ui-new-left.tmp"), "part of a backup")
    [IO.File]::WriteAllText((Join-Path $folder "swkotor.ini.kotor-ui-new-left.tmp"), "part of a write")
    $iniBefore = Get-Sha (Join-Path $folder "swkotor.ini")
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds: there is no backup yet"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "and its restore"
    Assert ((Get-Sha (Join-Path $folder "swkotor.ini")) -eq $iniBefore) "swkotor.ini is as it was"
    Assert (@(Get-ChildItem -LiteralPath $folder -Recurse -File -Filter "*.tmp").Count -eq 0) "what a stopped write left is gone"

    Write-Host "Case 18 a damaged manifest stops both, before anything changes (audit INS-05)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "damaged-manifest"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $manifest = Join-Path $folder "KMRP\kpm.manifest"
    $good = [IO.File]::ReadAllBytes($manifest)
    $installed = Get-Listing $folder | Where-Object { $_ -notmatch $kept }
    foreach ($damage in @(
        @{ name = "no version row"; lines = [IO.File]::ReadAllLines($manifest) | Select-Object -Skip 1 },
        @{ name = "a row naming a file outside the game"; lines = @([IO.File]::ReadAllLines($manifest)) + "file`t..\..\elsewhere.txt`t00" })) {
        [IO.File]::WriteAllLines($manifest, [string[]]$damage.lines)
        $damagedListing = Get-Listing $folder | Where-Object { $_ -notmatch $kept -and $_ -notmatch 'kpm\.manifest' }
        Assert ((Invoke-Installer @("--restore", "`"$game`"")) -ne 0) "$($damage.name): the restore refuses"
        Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -ne 0) "$($damage.name): the install refuses"
        Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 3) "$($damage.name): the window says so"
        $now = Get-Listing $folder | Where-Object { $_ -notmatch $kept -and $_ -notmatch 'kpm\.manifest' }
        Assert (($now -join "`n") -eq ($damagedListing -join "`n")) "$($damage.name): nothing changed"
        Assert (Test-Path -LiteralPath $manifest) "$($damage.name): the manifest is kept"
    }
    [IO.File]::WriteAllBytes($manifest, $good)
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "with the manifest whole again the restore succeeds"

    Write-Host "Case 19 what a restore cannot put back, it says (audit INS-05, INS-08, INS-09)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "not-restored"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    [IO.File]::Delete((Join-Path $folder "binkw32Hooked.dll"))
    [IO.File]::Delete((Join-Path $folder "KMRP\backups\swkotor.ini"))
    [IO.File]::Delete((Join-Path $folder "KMRP\backups\swkotor.ini.sha256"))
    # A standalone K1DC's record may name files beside the game and nothing else.
    $victim = Join-Path $WorkRoot "not-the-games-file.txt"
    [IO.File]::WriteAllText($victim, "someone else's")
    [IO.File]::WriteAllText((Join-Path $folder "KMRP\driver-compat.manifest"),
        "version`t2.0.1-win7`r`n..\not-the-games-file.txt`t$(Get-Sha $victim)`r`n")
    # A restore of the old standalone's Override that stopped after this file went back.
    $override = Join-Path $folder "Override"
    $backupFolder = Join-Path $folder "KOTOR_UI_Override_Backup"
    New-Item -ItemType Directory -Force -Path $override, $backupFolder | Out-Null
    [IO.File]::WriteAllText((Join-Path $override "x.gui"), "the player's file")
    [IO.File]::WriteAllText((Join-Path $backupFolder "x.gui"), "the player's file")
    $name = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("x.gui"))
    [IO.File]::WriteAllText((Join-Path $folder "KOTOR_UI_Override_Backup.manifest"),
        "KUIOVERRIDE1`r`n$name`t1`t$(Get-Sha (Join-Path $override 'x.gui'))`t$('A' * 64)`r`n")
    $errorLog = Join-Path (Split-Path -Parent $Installer) "KMRP.startup-error.log"
    if (Test-Path -LiteralPath $errorLog) { [IO.File]::Delete($errorLog) }
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -ne 0) "the restore does not report success"
    $message = if (Test-Path -LiteralPath $errorLog) { [IO.File]::ReadAllText($errorLog) } else { "" }
    Assert ($message -match 'binkw32\.dll') "it names binkw32.dll"
    Assert ($message -match 'swkotor\.ini') "and swkotor.ini"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KMRP\kpm.manifest"))) "KMRP is removed all the same"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KotorPatcher.dll"))) "its runtime with it"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KOTOR_UI_Override_Backup.manifest"))) "an Override restore that stopped part way finishes"
    Assert (Test-Path -LiteralPath $victim) "a record naming a file outside the game folder deletes nothing"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -ne 0) "a new install asks for binkw32.dll"

    Write-Host "Case 20 the status goes by the files, not the manifest alone (audit INS-07)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "repair"
    $folder = Split-Path -Parent $game
    $gameBink = [IO.File]::ReadAllBytes((Join-Path $folder "binkw32.dll"))
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 0) "nothing installed: nothing to repair"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $proxy = [IO.File]::ReadAllBytes((Join-Path $folder "binkw32.dll"))
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 0) "a whole install needs none"
    [IO.File]::WriteAllBytes((Join-Path $folder "binkw32.dll"), $gameBink)
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 3) "Steam's own binkw32.dll back needs a repair"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the repair succeeds"
    Assert ((Get-Sha (Join-Path $folder "binkw32.dll")) -eq ([BitConverter]::ToString([Security.Cryptography.SHA256]::HashData($proxy)).Replace("-", ""))) "the proxy is back"
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 0) "and none is needed"
    [IO.File]::Delete((Join-Path $folder "patches\kmrp.dll"))
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 3) "a missing module needs a repair"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the repair succeeds"
    [IO.File]::Delete((Join-Path $folder "KMRP\controller.ini"))
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 0) "the player's settings file is not asked about"
    [IO.File]::AppendAllText((Join-Path $folder "patch_config.toml"), "`n")
    [IO.File]::Delete((Join-Path $folder "patches\kmrp-controller.dll"))
    Assert ((Invoke-Installer @("--needs-repair", "`"$game`"")) -eq 0) "an install KPM rewrote is KPM's"

    Write-Host "Case 21 nothing starts while the game or another installer has the folder (audit INS-06)"
    Set-KmrpSettings $true $true
    $game = New-Fixture "guarded"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    # A running program's file refuses to open for writing, as this does.
    $held = [IO.File]::Open($game, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $code = Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")
    $held.Dispose()
    Assert ($code -ne 0) "the install refuses while the game runs"
    Assert (([IO.File]::ReadAllText($errorLog)) -match 'KOTOR is running') "and says why"
    Assert (((Get-Listing $folder) -join "`n") -eq ($before -join "`n")) "nothing changed"
    $process = Start-Process -FilePath $Installer -ArgumentList @("--in-place", "`"$game`"", "1920x1080") -PassThru
    while (-not $process.HasExited -and -not (Test-Path -LiteralPath (Join-Path $folder "KMRP\kpm.manifest"))) { Start-Sleep -Milliseconds 5 }
    Assert (-not $process.HasExited) "the test caught the first installer running"
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -ne 0) "a second installer on the folder refuses"
    Assert (([IO.File]::ReadAllText($errorLog)) -match 'Another KMRP installer') "and says why"
    $process.WaitForExit()
    Assert ($process.ExitCode -eq 0) "the first finishes"
    $game2 = New-Fixture "guarded-other"
    Assert ((Invoke-Installer @("--in-place", "`"$game2`"", "1920x1080")) -eq 0) "another folder is free meanwhile"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the lock is released"
    $account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $locked = New-Fixture "no-rights"
    $lockedFolder = Split-Path -Parent $locked
    & icacls $lockedFolder /deny "${account}:(WD,AD)" | Out-Null
    try {
        Assert ((Invoke-Installer @("--in-place", "`"$locked`"", "1920x1080")) -ne 0) "a folder this account may not write to refuses"
        Assert (([IO.File]::ReadAllText($errorLog)) -match 'may not change files') "and says why"
    }
    finally {
        & icacls $lockedFolder /remove:d $account | Out-Null
    }
}
finally {
    $env:LOCALAPPDATA = $playerLocalAppData
    if ($hadKmrp) { Copy-Item -LiteralPath $kmrpCopy -Destination $kmrpSettings -Force }
    elseif (Test-Path -LiteralPath $kmrpSettings) { [IO.File]::Delete($kmrpSettings) }
    if ($hadKpm) { Copy-Item -LiteralPath $kpmCopy -Destination $kpmSettings -Force }
    elseif (Test-Path -LiteralPath $kpmSettings) { [IO.File]::Delete($kpmSettings) }
    # The folder, and the DPI value each fixture's install left, keyed by its path. Each run
    # stranded both until 2026-11-01: 165 MB a run, 20 folders by then. Kept on a failure, to look at.
    if ($script:failures -eq 0) {
        $layers = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(
            'Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers', $true)
        if ($layers) {
            foreach ($name in $layers.GetValueNames()) {
                if ($name.StartsWith($WorkRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) { $layers.DeleteValue($name, $false) }
            }
            $layers.Dispose()
        }
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

if ($script:failures -gt 0) {
    Write-Host "FAILED ($($script:failures))" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED" -ForegroundColor Green
exit 0
