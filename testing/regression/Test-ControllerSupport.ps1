<#
    Structural and ownership regression for optional Xbox Controller Support.

    Temporarily enables the persistent option, installs into isolated game
    folders, validates all runtime files/config/hooks, restores them, and proves
    an unrelated patch_config.toml is never overwritten.
#>
[CmdletBinding()]
param(
    [string]$Patcher  = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$CleanExe = ".\build-inputs\swkotornopatch.exe",
    [string]$SeedIni  = ".\testing\virtual-display\swkotor-7680-windowed.ini",
    [string]$Resolution = "1920x1080",
    [string]$WorkRoot,
    [switch]$KeepWorkRoot,
    [switch]$LeaveInstalled
)

$ErrorActionPreference = "Stop"
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

function New-Install([string]$name) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    Copy-Item -LiteralPath $CleanExe -Destination (Join-Path $folder "swkotor.exe")
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    return Join-Path $folder "swkotor.exe"
}

$Patcher = Resolve-Input $Patcher
$CleanExe = Resolve-Input $CleanExe
$SeedIni = Resolve-Input $SeedIni
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([IO.Path]::GetTempPath()) ("kmrp-controller-" + [Guid]::NewGuid().ToString("N"))
}
$WorkRoot = [IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

$settingsPath = Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)) "KMRP\settings.json"
$settingsExisted = Test-Path -LiteralPath $settingsPath
$settingsBytes = if ($settingsExisted) { [IO.File]::ReadAllBytes($settingsPath) } else { $null }
$controllerNames = @("kmrp-controller-runtime.asi", "kmrp-controller.module", "patch_config.toml", "KMRP_Controller.manifest")

try {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $settingsPath) | Out-Null
    [IO.File]::WriteAllText($settingsPath, "{`r`n  `"driverCompatibility`": true,`r`n  `"markerFixes`": true,`r`n  `"controllerSupport`": true`r`n}`r`n", [Text.UTF8Encoding]::new($false))

    Write-Host ""
    Write-Host ("Controller support regression  ->  " + $WorkRoot)
    Write-Host "Case 1  install and restore the owned runtime"
    $game = New-Install "standard"
    $folder = Split-Path -Parent $game
    Assert ((Invoke-Patcher @("--in-place", $game, $Resolution)) -eq 0) "controller-enabled in-place patch succeeds"
    foreach ($name in $controllerNames) {
        Assert (Test-Path -LiteralPath (Join-Path $folder $name)) ("installed " + $name)
    }
    Assert (Test-Path -LiteralPath (Join-Path $folder "dinput8.dll")) "required ASI loader is installed"

    $configPath = Join-Path $folder "patch_config.toml"
    $config = [IO.File]::ReadAllText($configPath)
    Assert (($config | Select-String -AllMatches '\[\[patches\.hooks\]\]').Matches.Count -eq 8) "config contains exactly eight detours"
    Assert (($config | Select-String -AllMatches '\[\[patches\.hooks\.parameters\]\]').Matches.Count -eq 13) "config contains all thirteen hook parameters"
    python -c "import sys,tomllib; d=tomllib.load(open(sys.argv[1],'rb')); assert len(d['patches'])==1 and len(d['patches'][0]['hooks'])==8" $configPath
    Assert ($LASTEXITCODE -eq 0) "generated hook config parses as TOML"

    $bytes = [IO.File]::ReadAllBytes($game)
    $sites = @(
        @{ Va = 0x005E271E; Hex = "8B8424E4000000" },
        @{ Va = 0x006227E0; Hex = "6AFF68E9897200" },
        @{ Va = 0x004051C3; Hex = "8BC683E81C" },
        @{ Va = 0x00404D96; Hex = "8B46488B4808" },
        @{ Va = 0x00686BA0; Hex = "5356578BF1" },
        @{ Va = 0x0068B170; Hex = "6AFF68B0F77200" },
        @{ Va = 0x0040C1F6; Hex = "891E897E04" },
        @{ Va = 0x0040A638; Hex = "8B4F1C3BCE" }
    )
    foreach ($site in $sites) {
        $expected = [Convert]::FromHexString($site.Hex)
        $offset = $site.Va - 0x00400000
        $actual = [byte[]]::new($expected.Length)
        [Buffer]::BlockCopy($bytes, $offset, $actual, 0, $actual.Length)
        Assert ([Convert]::ToHexString($actual) -eq $site.Hex) ("hook bytes intact at VA 0x{0:X8}" -f $site.Va)
    }

    if (-not $LeaveInstalled) {
        Assert ((Invoke-Patcher @("--restore", $game)) -eq 0) "restore succeeds"
        foreach ($name in $controllerNames) {
            Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("restore removed " + $name)
        }
    }

    Write-Host ""
    Write-Host "Case 2  an unrelated KPM config is preserved"
    $conflictGame = New-Install "config-conflict"
    $conflictFolder = Split-Path -Parent $conflictGame
    $conflictPath = Join-Path $conflictFolder "patch_config.toml"
    $sentinel = "# user-owned KPM configuration`r`n"
    [IO.File]::WriteAllText($conflictPath, $sentinel, [Text.UTF8Encoding]::new($false))
    $cleanHash = (Get-FileHash -LiteralPath $conflictGame -Algorithm SHA256).Hash
    Assert ((Invoke-Patcher @("--in-place", $conflictGame, $Resolution)) -eq 1) "foreign config blocks installation"
    Assert ([IO.File]::ReadAllText($conflictPath) -eq $sentinel) "foreign config remains byte-for-byte in place"
    Assert ((Get-FileHash -LiteralPath $conflictGame -Algorithm SHA256).Hash -eq $cleanHash) "failed install rolls the executable back"
    Assert (-not (Test-Path -LiteralPath (Join-Path $conflictFolder "KMRP_Controller.manifest"))) "failed install claims no controller ownership"
    Assert (-not (Test-Path -LiteralPath (Join-Path $conflictFolder "KMRP_DriverCompat.manifest"))) "failed install rolls the ASI loader back"
}
finally {
    if ($settingsExisted) { [IO.File]::WriteAllBytes($settingsPath, $settingsBytes) }
    elseif (Test-Path -LiteralPath $settingsPath) { Remove-Item -LiteralPath $settingsPath -Force }

    if (-not $KeepWorkRoot -and (Test-Path -LiteralPath $WorkRoot)) {
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
        if (-not $WorkRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a test directory outside the system temp root: $WorkRoot"
        }
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
}

if ($script:Failures -ne 0) { throw "$($script:Failures) controller regression check(s) failed." }
Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
