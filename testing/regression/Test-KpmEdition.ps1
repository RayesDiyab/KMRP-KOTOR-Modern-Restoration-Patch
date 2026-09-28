<#
    The KPM edition: its installer, and that it makes the same game as the standalone.

    KMRP ships two ways from one source (tools/build_kpatch.py, src/patcher/KpmEdition.cs).
    The KPM edition's installer leaves swkotor.exe unmodified and writes kmrp-kpm.dat,
    which KMRP's module applies in memory under KOTOR Patch Manager -- the parts of
    KMRP Movies and KMRP Map Notes only when those patches are ticked there. This
    proves, per resolution, on isolated fixture folders:

      1. the install leaves the executable byte-for-byte unmodified, installs the
         Override files, swkotor.ini's resolution, the data file and SDL, and none
         of the standalone's runtime (no patch_config.toml, ASI loader or module);
      2. the data file makes EXACTLY the standalone installer's executable for the
         same resolution: tools/kpm_data.py applies it to the clean executable as the
         module does and compares every byte of the original sections and the
         eleven appended ones with `--apply`'s output -- with all four patches, the
         standalone with the marker fixes on; without Map Notes, the standalone with
         them off; without Movies, the same less exactly the movie sites. The KPM
         install is made with the standalone's marker setting OFF, to prove the
         KPM edition does not read it;
      3. the Movies and Map Notes parts are exactly the sites they should be: the
         four movie display-mode operands and the movie aspect fit's entry, and the
         .kmn flag;
      4. reinstalling at another resolution replaces the data file;
      5. restore removes every file it installed and leaves the executable as it was;
      6. a game the standalone installer patched is refused, and left untouched.

    The standalone reads its options from %LOCALAPPDATA%\KMRP\settings.json; this
    copies the player's file aside first and puts it back at the end.

    It does not run the game; the in-game check is tools/kpm_data.py --memory against
    a running game launched through KOTOR Patch Manager.
#>
[CmdletBinding()]
param(
    [string]$KpmInstaller = ".\dist\KMRP for KPM\KMRP for KPM.exe",
    [string]$Standalone   = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$CleanExe     = ".\build-inputs\swkotornopatch.exe",
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

function New-Fixture([string]$name) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    # A fixture name, so no NVIDIA profile made for it can match a real swkotor.exe.
    Copy-Item -LiteralPath $CleanExe -Destination (Join-Path $folder "kmrp-kpm-selftest.exe")
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    return Join-Path $folder "kmrp-kpm-selftest.exe"
}

# The standalone's saved options; only the marker fixes differ between cases.
function Set-MarkerFixes([bool]$on) {
    $value = if ($on) { "true" } else { "false" }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $settingsPath) | Out-Null
    [IO.File]::WriteAllText($settingsPath, "{`r`n  `"driverCompatibility`": true,`r`n  `"markerFixes`": $value,`r`n  `"controllerSupport`": true`r`n}`r`n", [Text.UTF8Encoding]::new($false))
}

function Test-Equals([string]$dat, [string]$standaloneExe, [string]$features, [string]$label) {
    python tools\kpm_data.py $dat --clean $CleanExe --equals $standaloneExe --features $features
    Assert ($LASTEXITCODE -eq 0) $label
}

$KpmInstaller = Resolve-Input $KpmInstaller
$Standalone = Resolve-Input $Standalone
$CleanExe = Resolve-Input $CleanExe
$SeedIni = Resolve-Input $SeedIni
$cleanHash = (Get-FileHash -LiteralPath $CleanExe -Algorithm SHA256).Hash
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("kmrp-kpm-" + [Guid]::NewGuid().ToString("N"))
}
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$standaloneOnly = @("patch_config.toml", "dinput8.dll", "kmrp-controller-runtime.asi", "kmrp-controller.module",
    "k1-modern-driver-compatibility.asi", "KMRP_Controller.manifest")
$settingsPath = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "KMRP\settings.json"
$settingsExisted = Test-Path -LiteralPath $settingsPath
# A copy on disk rather than in memory: it survives this script being stopped.
$settingsCopy = Join-Path $WorkRoot "player-settings.json"
if ($settingsExisted) { Copy-Item -LiteralPath $settingsPath -Destination $settingsCopy }

# Where KMRP Movies and KMRP Map Notes may write: the movie display-mode operands
# (imm32, VA 0x00403D6C, 0x00403D78, 0x005F5B3B, 0x005F5B43), the jump into the movie
# aspect fit (0x004057AC, 7 bytes), and the .kmn enable flag (0x00876000, 4 bytes).
$movieSites = @(@(0x00403D6C, 4), @(0x00403D78, 4), @(0x005F5B3B, 4), @(0x005F5B43, 4), @(0x004057AC, 7))

try {
    Write-Host ""
    Write-Host ("KPM edition regression  ->  " + $WorkRoot)
    foreach ($resolution in $Resolutions) {
        Write-Host ("Case 1-2  install at {0}, and the same game as the standalone" -f $resolution)
        $game = New-Fixture ("kpm-" + $resolution)
        $folder = Split-Path -Parent $game
        $dat = Join-Path $folder "kmrp-kpm.dat"
        Set-MarkerFixes $false
        Assert ((Invoke-Exe $KpmInstaller @("--in-place", $game, $resolution)) -eq 0) "the KPM edition installs (standalone marker setting off)"
        Assert ((Get-FileHash -LiteralPath $game -Algorithm SHA256).Hash -eq $cleanHash) "swkotor.exe is byte-for-byte unmodified"
        foreach ($name in @("kmrp-kpm.dat", "KMRP_KPM.manifest", "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt")) {
            Assert (Test-Path -LiteralPath (Join-Path $folder $name)) ("installed " + $name)
        }
        foreach ($name in $standaloneOnly) {
            Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("no standalone runtime file " + $name)
        }
        Assert ((@(Get-ChildItem -LiteralPath (Join-Path $folder "Override") -File -ErrorAction SilentlyContinue)).Count -gt 1000) "the Override files are installed"
        $width, $height = $resolution -split "x"
        $ini = [IO.File]::ReadAllText((Join-Path $folder "swkotor.ini"))
        Assert ($ini -match "(?m)^Width=$width\r?$" -and $ini -match "(?m)^Height=$height\r?$") "swkotor.ini carries the resolution"

        $standaloneOff = Join-Path $WorkRoot ("standalone-nomarkers-" + $resolution + ".exe")
        Assert ((Invoke-Exe $Standalone @("--apply", $CleanExe, $standaloneOff, $resolution)) -eq 0) "the standalone builds its executable, marker fixes off"
        Set-MarkerFixes $true
        $standaloneOut = Join-Path $WorkRoot ("standalone-" + $resolution + ".exe")
        Assert ((Invoke-Exe $Standalone @("--apply", $CleanExe, $standaloneOut, $resolution)) -eq 0) "the standalone builds its executable, marker fixes on"
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
    $before = (Get-FileHash -LiteralPath (Join-Path $folder "kmrp-kpm.dat")).Hash
    Assert ((Invoke-Exe $KpmInstaller @("--in-place", $game, $Resolutions[1])) -eq 0) "reinstall at another resolution succeeds"
    Assert ((Get-FileHash -LiteralPath (Join-Path $folder "kmrp-kpm.dat")).Hash -ne $before) "the data file was replaced"
    $standaloneOut = Join-Path $WorkRoot ("standalone-" + $Resolutions[1] + ".exe")
    Test-Equals (Join-Path $folder "kmrp-kpm.dat") $standaloneOut "kmrp,kmrp-movies,kmrp-map-notes" "the new data file is the new resolution's"

    Write-Host "Case 5  restore"
    foreach ($resolution in $Resolutions) {
        $game = Join-Path (Join-Path $WorkRoot ("kpm-" + $resolution)) "kmrp-kpm-selftest.exe"
        $folder = Split-Path -Parent $game
        Assert ((Invoke-Exe $KpmInstaller @("--restore", $game)) -eq 0) ("restore succeeds (" + $resolution + " fixture)")
        foreach ($name in @("kmrp-kpm.dat", "KMRP_KPM.manifest", "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt")) {
            Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("restore removed " + $name)
        }
        Assert ((@(Get-ChildItem -LiteralPath (Join-Path $folder "Override") -File -ErrorAction SilentlyContinue)).Count -eq 0) "restore emptied Override"
        Assert ((Get-FileHash -LiteralPath $game -Algorithm SHA256).Hash -eq $cleanHash) "swkotor.exe is still unmodified"
    }

    Write-Host "Case 6  a game the standalone patched is refused"
    $gold = New-Fixture "standalone-installed"
    Assert ((Invoke-Exe $Standalone @("--in-place", $gold, $Resolutions[0])) -eq 0) "the standalone installs"
    $goldHash = (Get-FileHash -LiteralPath $gold -Algorithm SHA256).Hash
    Assert ((Invoke-Exe $KpmInstaller @("--in-place", $gold, $Resolutions[0])) -ne 0) "the KPM edition refuses it"
    Assert ((Get-FileHash -LiteralPath $gold -Algorithm SHA256).Hash -eq $goldHash) "and leaves its executable alone"
    Assert (-not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $gold) "kmrp-kpm.dat"))) "and writes no data file"
    Assert ((Invoke-Exe $Standalone @("--restore", $gold)) -eq 0) "the standalone restores it"
}
finally {
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

if ($script:Failures -ne 0) { throw "$($script:Failures) KPM edition check(s) failed." }
Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
