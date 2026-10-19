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

    Case 8 (2026-10-19): Modern Driver Compatibility on, off in every case above: the
    installer writes Synchro's two files, byte for byte the vendored 2.0.0 standalone
    build, beside the game with their manifest, and Restore Original removes them.
    Case 9 (2026-10-19): the same on a PC that lacks a function K1DC imports (Windows 7,
    faked with KMRP_TEST_MISSING_IMPORT): the install succeeds and writes neither file.
    Case 10 (2026-10-19): Marked Empty Containers on, off in every case above (its default
    is on): ShaeMyName's patch is the third in patch_config.toml with its one hook and no
    DLL, nothing of it goes into patches\, its .kpatch is the bundled file, and Restore
    Original removes all of it.

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
if (-not $Installer) { $Installer = Join-Path $projectRoot "dist\KMRP - KOTOR Modern Restoration Patch.exe" }
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
function New-Fixture([string]$name) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    Copy-Item -LiteralPath $SourceExe -Destination (Join-Path $folder "swkotor.exe")
    [IO.File]::WriteAllBytes((Join-Path $folder "binkw32.dll"), [byte[]](1..64))
    [IO.File]::WriteAllText((Join-Path $folder "swkotor.ini"),
        "[Graphics Options]`r`nFullScreen=1`r`nWidth=800`r`nHeight=600`r`n", [Text.UTF8Encoding]::new($false))
    return (Join-Path $folder "swkotor.exe")
}
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

    Write-Host "Case 4  Restore Original"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch 'swkotor\.ini\.kotor-ui-backup' }
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
    $after = Get-Listing $folder | Where-Object { $_ -notmatch 'swkotor\.ini\.kotor-ui-backup' }
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
    Assert ([IO.File]::ReadAllText((Join-Path $folder "KMRP_KPM.manifest")) -match ('(?m)^built\t' + [regex]::Escape($stamp) + '\r?$')) "the manifest records this build's date ($stamp)"
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
    $after = Get-Listing $folder | Where-Object { $_ -notmatch 'swkotor\.ini\.kotor-ui-backup' }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"

    Write-Host "Case 8  Modern Driver Compatibility on"
    Set-KmrpSettings $true $true "" "" $false $true
    $game = New-Fixture "driver-compat"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds"
    $vendored = Join-Path $projectRoot "third_party\Included\k1-modern-driver-compatibility-2.0.0 by Synchro"
    foreach ($name in @("dinput8.dll", "k1-modern-driver-compatibility.asi")) {
        $installed = Join-Path $folder $name
        Assert ((Test-Path -LiteralPath $installed) -and (Get-Sha $installed) -eq (Get-Sha (Join-Path $vendored $name))) "$name is the vendored K1 Modern Driver Compatibility 2.0.0 file"
    }
    $manifest = Join-Path $folder "KMRP_DriverCompat.manifest"
    Assert ((Test-Path -LiteralPath $manifest) -and ([IO.File]::ReadAllText($manifest) -match '(?m)^version\t2\.0\.0\r?$')) "KMRP_DriverCompat.manifest records version 2.0.0"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch 'swkotor\.ini\.kotor-ui-backup' }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file: both files and the manifest are gone"

    Write-Host "Case 9  Modern Driver Compatibility on, on a PC that cannot run it"
    # KMRP_TEST_MISSING_IMPORT counts one of K1DC's Windows 8 functions as missing, the
    # answer Windows 7 gives (DriverCompatOperations.MissingImport). Start-Process passes
    # the variable to the installer.
    Set-KmrpSettings $true $true "" "" $false $true
    $game = New-Fixture "driver-compat-windows7"
    $folder = Split-Path -Parent $game
    $before = Get-Listing $folder
    $env:KMRP_TEST_MISSING_IMPORT = "CreateFile2"
    try { Assert ((Invoke-Installer @("--in-place", "`"$game`"", "1920x1080")) -eq 0) "the install succeeds without it" }
    finally { Remove-Item Env:KMRP_TEST_MISSING_IMPORT -ErrorAction SilentlyContinue }
    foreach ($name in @("dinput8.dll", "k1-modern-driver-compatibility.asi", "KMRP_DriverCompat.manifest")) {
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) "no $name beside the game"
    }
    Assert (((Get-Config $folder).Ids -join ",") -eq "kmrp,kmrp-controller") "KMRP's patch and the controller patch are installed as usual"
    Assert ((Invoke-Installer @("--restore", "`"$game`"")) -eq 0) "the restore succeeds"
    $after = Get-Listing $folder | Where-Object { $_ -notmatch 'swkotor\.ini\.kotor-ui-backup' }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"

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
    $after = Get-Listing $folder | Where-Object { $_ -notmatch 'swkotor\.ini\.kotor-ui-backup' }
    Assert (($after -join "`n") -eq ($before -join "`n")) "the folder is as it was, file for file"
    Assert (-not (Test-Path -LiteralPath $emptyKpatch)) "the .kpatch this install created is removed"
}
finally {
    $env:LOCALAPPDATA = $playerLocalAppData
    if ($hadKmrp) { Copy-Item -LiteralPath $kmrpCopy -Destination $kmrpSettings -Force }
    elseif (Test-Path -LiteralPath $kmrpSettings) { [IO.File]::Delete($kmrpSettings) }
    if ($hadKpm) { Copy-Item -LiteralPath $kpmCopy -Destination $kpmSettings -Force }
    elseif (Test-Path -LiteralPath $kpmSettings) { [IO.File]::Delete($kpmSettings) }
}

if ($script:failures -gt 0) {
    Write-Host "FAILED ($($script:failures))" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED" -ForegroundColor Green
exit 0
