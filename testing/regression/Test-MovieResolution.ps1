<#
    Regression coverage for KOTOR's separate full-screen movie display mode.

    KMRP must write the selected width and height to both verified movie-mode
    operand pairs.  The normal render-resolution operands are checked alongside
    them so a future refactor cannot accidentally update only one subsystem.
#>
[CmdletBinding()]
param(
    [string]$Patcher  = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$CleanExe = ".\build-inputs\swkotornopatch.exe",
    [string]$WorkRoot,
    [switch]$KeepWorkRoot
)

$ErrorActionPreference = "Stop"
$script:Failures = 0

function Resolve-Input([string]$path) {
    return (Resolve-Path -LiteralPath $path).Path
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

function Read-Int32([string]$path, [int]$offset) {
    $stream = [System.IO.File]::OpenRead($path)
    try {
        $stream.Position = $offset
        $buffer = [byte[]]::new(4)
        if ($stream.Read($buffer, 0, 4) -ne 4) { throw "Short read at 0x$($offset.ToString('X'))." }
        return [BitConverter]::ToInt32($buffer, 0)
    }
    finally { $stream.Dispose() }
}

function Assert([bool]$condition, [string]$message) {
    if ($condition) {
        Write-Host ("  PASS  " + $message) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  " + $message) -ForegroundColor Red
        $script:Failures++
    }
}

$Patcher = Resolve-Input $Patcher
$CleanExe = Resolve-Input $CleanExe
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-movies-" + [Guid]::NewGuid().ToString("N"))
}
$WorkRoot = [System.IO.Path]::GetFullPath($WorkRoot)
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

$widthOffsets = @(0x00003D6C, 0x001F5B3B)
$heightOffsets = @(0x00003D78, 0x001F5B43)
$normalWidthOffsets = @(0x0000AA65, 0x001F0C65)
$normalHeightOffsets = @(0x0000AA85, 0x001F0C6F)
$cases = @(
    @{ Key = "800x600"; Width = 800; Height = 600 },
    @{ Key = "1920x1080"; Width = 1920; Height = 1080 },
    @{ Key = "3440x1440"; Width = 3440; Height = 1440 },
    @{ Key = "3840x2160"; Width = 3840; Height = 2160 }
)

try {
    Write-Host ""
    Write-Host ("Movie display-mode regression  ->  " + $WorkRoot)
    foreach ($case in $cases) {
        $output = Join-Path $WorkRoot ("swkotor-" + $case.Key + ".exe")
        Assert ((Invoke-Patcher @("--apply", $CleanExe, $output, $case.Key)) -eq 0) ("{0} patches successfully" -f $case.Key)
        foreach ($offset in $widthOffsets) {
            Assert ((Read-Int32 $output $offset) -eq $case.Width) ("{0} movie width at FILE 0x{1:X}" -f $case.Key, $offset)
        }
        foreach ($offset in $heightOffsets) {
            Assert ((Read-Int32 $output $offset) -eq $case.Height) ("{0} movie height at FILE 0x{1:X}" -f $case.Key, $offset)
        }
        foreach ($offset in $normalWidthOffsets) {
            Assert ((Read-Int32 $output $offset) -eq $case.Width) ("{0} render width at FILE 0x{1:X}" -f $case.Key, $offset)
        }
        foreach ($offset in $normalHeightOffsets) {
            Assert ((Read-Int32 $output $offset) -eq $case.Height) ("{0} render height at FILE 0x{1:X}" -f $case.Key, $offset)
        }
    }
}
finally {
    if (-not $KeepWorkRoot -and (Test-Path -LiteralPath $WorkRoot)) {
        $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
        if (-not $WorkRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove a test directory outside the system temp root: $WorkRoot"
        }
        Remove-Item -LiteralPath $WorkRoot -Recurse -Force
    }
}

if ($script:Failures -ne 0) {
    throw "$($script:Failures) movie display-mode regression check(s) failed."
}
Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
