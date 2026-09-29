<#
.SYNOPSIS
    Regression tests for KMRP's per-executable Windows DPI compatibility setting.

.DESCRIPTION
    Exercises the public patcher commands against throwaway game directories. The
    tests prove that KMRP adds HIGHDPIAWARE, preserves an existing compatibility
    string byte-for-byte on restore, does not overwrite a later user change, and
    rolls the registry back when its DPI manifest cannot be written.

    Registry cleanup is limited to the exact throwaway swkotor.exe paths used by
    this run. Their pre-test values are captured and restored in finally.
#>
[CmdletBinding()]
param(
    [string]$Patcher    = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$CleanExe   = ".\build-inputs\swkotornopatch.exe",
    [string]$SeedIni    = ".\testing\virtual-display\swkotor-7680-windowed.ini",
    [string]$Resolution = "1920x1080",
    [string]$WorkRoot,
    [switch]$KeepWorkRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Restore-TestNvidiaProfiles.ps1")
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$layersPath = "Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
$manifestName = "KMRP_DPI.manifest"
$script:Failures = 0
$script:OriginalValues = @{}

function Resolve-Input([string]$path) {
    if ([System.IO.Path]::IsPathRooted($path)) { return $path }
    return (Join-Path $projectRoot $path)
}

function Get-LayerValue([string]$exePath) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($layersPath, $false)
    try {
        if ($null -eq $key) { return [pscustomobject]@{ Exists = $false; Value = $null } }
        $names = $key.GetValueNames()
        if ($names -notcontains $exePath) { return [pscustomobject]@{ Exists = $false; Value = $null } }
        return [pscustomobject]@{
            Exists = $true
            Value = [string]$key.GetValue($exePath, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        }
    }
    finally {
        if ($null -ne $key) { $key.Dispose() }
    }
}

function Set-LayerValue([string]$exePath, [bool]$exists, [string]$value) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($layersPath)
    try {
        if ($exists) {
            $key.SetValue($exePath, $value, [Microsoft.Win32.RegistryValueKind]::String)
        } else {
            $key.DeleteValue($exePath, $false)
        }
    }
    finally {
        $key.Dispose()
    }
}

function Assert([bool]$condition, [string]$message) {
    if ($condition) {
        Write-Host ("  PASS  " + $message) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  " + $message) -ForegroundColor Red
        $script:Failures++
    }
}

function Invoke-Patcher([string[]]$patcherArgs) {
    $process = Start-Process -FilePath $Patcher -ArgumentList $patcherArgs -Wait -PassThru -WindowStyle Hidden
    return $process.ExitCode
}

function New-Install([string]$name) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $exe = Join-Path $folder "kmrp-regression-selftest.exe"
    Copy-Item -LiteralPath $CleanExe -Destination $exe
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    # KMRP's installer renames the game's binkw32.dll to put KOTOR Patch Manager's
    # proxy in its place, and puts it back on restore; any bytes stand in for it.
    [IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
    $script:OriginalValues[$exe] = Get-LayerValue $exe
    return $exe
}

$Patcher = Resolve-Input $Patcher
$CleanExe = Resolve-Input $CleanExe
$SeedIni = Resolve-Input $SeedIni
foreach ($required in @($Patcher, $CleanExe, $SeedIni)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required input is missing: $required" }
}
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-dpi-" + [Guid]::NewGuid().ToString("N"))
}
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

Write-Host ""
Write-Host ("DPI compatibility regression  ->  " + $WorkRoot)

# KPM's own settings, parked for the run (Restore-TestNvidiaProfiles.ps1).
$kpmLauncherSettings = Hide-KpmLauncherSettings $WorkRoot
try {
    Write-Host ""
    Write-Host "Case 1  no previous compatibility value"
    $exe = New-Install "case1"
    Set-LayerValue $exe $false $null
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    $current = Get-LayerValue $exe
    Assert ($exitCode -eq 0) "patch succeeded (exit $exitCode)"
    Assert ($current.Exists -and $current.Value -eq "HIGHDPIAWARE") "application DPI awareness was installed"
    Assert (Test-Path -LiteralPath (Join-Path (Split-Path $exe) $manifestName) -PathType Leaf) "restore manifest was written"
    $exitCode = Invoke-Patcher @("--restore", $exe)
    $current = Get-LayerValue $exe
    Assert ($exitCode -eq 0) "restore succeeded (exit $exitCode)"
    Assert (-not $current.Exists) "the newly created compatibility value was removed"
    Assert (-not (Test-Path -LiteralPath (Join-Path (Split-Path $exe) $manifestName))) "restore manifest was removed"

    Write-Host ""
    Write-Host "Case 2  an existing compatibility value"
    $exe = New-Install "case2"
    $previous = "~ DISABLETHEMES"
    Set-LayerValue $exe $true $previous
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    $current = Get-LayerValue $exe
    Assert ($exitCode -eq 0) "patch succeeded (exit $exitCode)"
    Assert ($current.Value -eq ($previous + " HIGHDPIAWARE")) "the DPI token was appended without replacing existing flags"
    $exitCode = Invoke-Patcher @("--restore", $exe)
    $current = Get-LayerValue $exe
    Assert ($exitCode -eq 0) "restore succeeded (exit $exitCode)"
    Assert ($current.Exists -and $current.Value -eq $previous) "the exact previous compatibility value was restored"

    Write-Host ""
    Write-Host "Case 3  the user changes the value after install"
    $exe = New-Install "case3"
    Set-LayerValue $exe $false $null
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "patch succeeded (exit $exitCode)"
    $userValue = "~ DISABLEDXMAXIMIZEDWINDOWEDMODE HIGHDPIAWARE"
    Set-LayerValue $exe $true $userValue
    $exitCode = Invoke-Patcher @("--restore", $exe)
    $current = Get-LayerValue $exe
    Assert ($exitCode -eq 0) "restore succeeded (exit $exitCode)"
    Assert ($current.Exists -and $current.Value -eq $userValue) "a later user change was left untouched"
    Assert (-not (Test-Path -LiteralPath (Join-Path (Split-Path $exe) $manifestName))) "the consumed restore manifest was removed"

    Write-Host ""
    Write-Host "Case 4  the restore manifest cannot be written"
    $exe = New-Install "case4"
    $previous = "~ DISABLETHEMES"
    Set-LayerValue $exe $true $previous
    $manifestPath = Join-Path (Split-Path $exe) $manifestName
    New-Item -ItemType Directory -Path $manifestPath | Out-Null
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    $current = Get-LayerValue $exe
    Assert ($exitCode -eq 0) "patch continued with the documented manual fallback (exit $exitCode)"
    Assert ($current.Exists -and $current.Value -eq $previous) "the unrecorded registry edit was rolled back"
}
finally {
    Restore-KpmLauncherSettings $kpmLauncherSettings
    Restore-TestNvidiaProfiles $WorkRoot
    foreach ($entry in $script:OriginalValues.GetEnumerator()) {
        Set-LayerValue $entry.Key $entry.Value.Exists $entry.Value.Value
    }
    # Kept fixtures keep their DPI values; --restore on each removes them.
    if (-not $KeepWorkRoot) { Remove-TestDpiValues $WorkRoot }
    if ($KeepWorkRoot) {
        Write-Host ""
        Write-Host ("work folder kept: " + $WorkRoot)
    } else {
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
if ($script:Failures -gt 0) {
    Write-Host ("$script:Failures check(s) failed.") -ForegroundColor Red
    exit 1
}
Write-Host "All checks passed." -ForegroundColor Green
exit 0
