<#
    Regression coverage for the PE Large Address Aware compatibility boundary.

    The accepted prepatched input differs from the canonical executable at one
    documented bit only. Both inputs must produce the same LAA KMRP output, and
    in-place restore must reproduce the exact input bytes rather than imposing
    one canonical state.
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
$characteristicsOffset = 0x926
$originalCharacteristics = 0x010F
$laaCharacteristics = 0x012F
$script:Failures = 0

function Resolve-Input([string]$path) {
    return (Resolve-Path -LiteralPath $path).Path
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Get-Characteristics([string]$path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    return [BitConverter]::ToUInt16($bytes, $characteristicsOffset)
}

function Set-Characteristics([string]$source, [string]$destination, [uint16]$value) {
    $bytes = [System.IO.File]::ReadAllBytes($source)
    if ([BitConverter]::ToUInt16($bytes, $characteristicsOffset) -ne $originalCharacteristics) {
        throw "Test source does not have the expected PE characteristics."
    }
    $replacement = [BitConverter]::GetBytes($value)
    $bytes[$characteristicsOffset] = $replacement[0]
    $bytes[$characteristicsOffset + 1] = $replacement[1]
    [System.IO.File]::WriteAllBytes($destination, $bytes)
}

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
    if ($condition) {
        Write-Host ("  PASS  " + $message) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  " + $message) -ForegroundColor Red
        $script:Failures++
    }
}

function New-Install([string]$name, [string]$source) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $exe = Join-Path $folder "kmrp-regression-selftest.exe"
    Copy-Item -LiteralPath $source -Destination $exe
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    return $exe
}

$Patcher = Resolve-Input $Patcher
$CleanExe = Resolve-Input $CleanExe
$SeedIni = Resolve-Input $SeedIni
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-laa-" + [Guid]::NewGuid().ToString("N"))
}
$WorkRoot = [System.IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

try {
    Write-Host ""
    Write-Host ("Large Address Aware regression  ->  " + $WorkRoot)

    $laaInput = Join-Path $WorkRoot "swkotor-laa-input.exe"
    $unsupportedInput = Join-Path $WorkRoot "swkotor-other-header-change.exe"
    Set-Characteristics $CleanExe $laaInput $laaCharacteristics
    Set-Characteristics $CleanExe $unsupportedInput 0x030F
    Assert ((Get-Characteristics $CleanExe) -eq $originalCharacteristics) "canonical input has PE characteristics 0x010F"
    Assert ((Get-Characteristics $laaInput) -eq $laaCharacteristics) "4 GB-patched input has PE characteristics 0x012F"

    Write-Host ""
    Write-Host "Case 1  clean and pre-LAA inputs converge on one output"
    $fromClean = Join-Path $WorkRoot "from-clean.exe"
    $fromLaa = Join-Path $WorkRoot "from-laa.exe"
    Assert ((Invoke-Patcher @("--apply", $CleanExe, $fromClean, $Resolution)) -eq 0) "canonical input patches successfully"
    Assert ((Invoke-Patcher @("--apply", $laaInput, $fromLaa, $Resolution)) -eq 0) "pre-LAA input patches successfully"
    Assert ((Get-Characteristics $fromClean) -eq $laaCharacteristics) "KMRP output enables IMAGE_FILE_LARGE_ADDRESS_AWARE"
    Assert ((Get-Sha256 $fromClean) -eq (Get-Sha256 $fromLaa)) "both supported inputs produce identical output"

    Write-Host ""
    Write-Host "Case 2  another PE-header modification remains unsupported"
    $unsupportedOutput = Join-Path $WorkRoot "unsupported-output.exe"
    Assert ((Invoke-Patcher @("--apply", $unsupportedInput, $unsupportedOutput, $Resolution)) -eq 1) "unrecognized header change is refused"
    Assert (-not (Test-Path -LiteralPath $unsupportedOutput)) "refused input produces no output file"

    Write-Host ""
    Write-Host "Case 3  in-place restore preserves the exact canonical input"
    $standardInstall = New-Install "standard" $CleanExe
    $standardHash = Get-Sha256 $standardInstall
    Assert ((Invoke-Patcher @("--in-place", $standardInstall, $Resolution)) -eq 0) "canonical in-place patch succeeds"
    Assert ((Get-Characteristics $standardInstall) -eq $laaCharacteristics) "in-place output is LAA"
    Assert ((Invoke-Patcher @("--restore", $standardInstall)) -eq 0) "canonical restore succeeds"
    Assert ((Get-Sha256 $standardInstall) -eq $standardHash) "restore reproduces the canonical input byte-for-byte"

    Write-Host ""
    Write-Host "Case 4  in-place restore preserves a pre-existing LAA input"
    $laaInstall = New-Install "pre-laa" $laaInput
    $laaHash = Get-Sha256 $laaInstall
    Assert ((Invoke-Patcher @("--in-place", $laaInstall, $Resolution)) -eq 0) "pre-LAA in-place patch succeeds"
    Assert ((Invoke-Patcher @("--restore", $laaInstall)) -eq 0) "pre-LAA restore succeeds"
    Assert ((Get-Sha256 $laaInstall) -eq $laaHash) "restore reproduces the pre-LAA input byte-for-byte"
}
finally {
    Restore-TestNvidiaProfiles $WorkRoot
    if (-not $KeepWorkRoot -and (Test-Path -LiteralPath $WorkRoot)) {
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if (-not $WorkRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a test directory outside the system temp root: $WorkRoot"
        }
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
}

if ($script:Failures -ne 0) {
    throw "$($script:Failures) Large Address Aware regression check(s) failed."
}
Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
