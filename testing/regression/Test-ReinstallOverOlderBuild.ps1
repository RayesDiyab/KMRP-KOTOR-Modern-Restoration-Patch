<#
.SYNOPSIS
    Regression test for reinstalling one KMRP build over another.

.DESCRIPTION
    A newer build installed over an older one used to be skipped: the sidecar's
    patchedSha256 still described the executable on disk accurately, so the
    install was judged "already patched" and only the sidecar was rewritten. The
    executable kept its old bytes and --in-place exited 0 while changing nothing.

    Case 1 reproduces exactly that shape -- an executable whose bytes are not the
    ones this build produces, with a sidecar that describes those bytes honestly
    -- and requires the executable to end up rebuilt. Cases 2 to 4 pin the
    behaviour that had to survive the fix: an up-to-date install is left alone, an
    unsupported executable is still refused, and a damaged backup still blocks a
    patch.

    Every check is made on the SHA-256 of the file, never on the sidecar.

.EXAMPLE
    .\testing\regression\Test-ReinstallOverOlderBuild.ps1
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
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Resolve-Input([string]$path) {
    if ([System.IO.Path]::IsPathRooted($path)) { return $path }
    return (Join-Path $projectRoot $path)
}

$Patcher  = Resolve-Input $Patcher
$CleanExe = Resolve-Input $CleanExe
$SeedIni  = Resolve-Input $SeedIni

foreach ($required in @($Patcher, $CleanExe, $SeedIni)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required input is missing: $required"
    }
}

if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-reinstall-" + [Guid]::NewGuid().ToString("N"))
}

$script:Failures = 0

function Get-Sha256([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
}

function Assert([bool]$condition, [string]$message) {
    if ($condition) {
        Write-Host ("  PASS  " + $message) -ForegroundColor Green
    } else {
        Write-Host ("  FAIL  " + $message) -ForegroundColor Red
        $script:Failures++
    }
}

# The patcher is a Windows subsystem binary, so its exit code has to come from
# the process object rather than from $LASTEXITCODE.
function Invoke-Patcher([string[]]$patcherArgs) {
    $process = Start-Process -FilePath $Patcher -ArgumentList $patcherArgs -Wait -PassThru -NoNewWindow
    return $process.ExitCode
}

# A throwaway game folder: swkotor.exe plus the swkotor.ini the patcher requires.
function New-Install([string]$name) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $exe = Join-Path $folder "swkotor.exe"
    Copy-Item -LiteralPath $CleanExe -Destination $exe
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    return $exe
}

New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
Write-Host ""
Write-Host ("Reinstall regression  ->  " + $WorkRoot)
Write-Host ("resolution " + $Resolution)

try {
    # ---------------------------------------------------------------- case 1
    # A newer build over an older one. The older build's output is simulated by
    # editing the installed executable and then rewriting the sidecar to match,
    # which is the state the real bug was reported in: a sidecar entirely
    # truthful about a file this build did not produce.
    Write-Host ""
    Write-Host "Case 1  reinstalling over an executable from a different build"
    $exe = New-Install "case1"
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "first patch succeeded (exit $exitCode)"
    $expected = Get-Sha256 $exe
    $manifest = $exe + ".kotor-ui-patch.json"

    $bytes = [System.IO.File]::ReadAllBytes($exe)
    $offset = 0x300000
    $bytes[$offset] = [byte](($bytes[$offset] + 1) % 256)
    [System.IO.File]::WriteAllBytes($exe, $bytes)
    $stale = Get-Sha256 $exe
    Assert ($stale -ne $expected) "the simulated older build differs from this build's output"

    # Make the sidecar describe the edited file exactly, and drop the build stamp
    # that a sidecar written by an older build would not have carried.
    $json = Get-Content -LiteralPath $manifest -Raw
    $json = [regex]::Replace($json, '"patchedSha256"\s*:\s*"[0-9A-Fa-f]{64}"', '"patchedSha256": "' + $stale + '"')
    $json = [regex]::Replace($json, '\s*"goldTargetSha256"\s*:\s*"[0-9A-Fa-f]{64}",', '')
    Set-Content -LiteralPath $manifest -Value $json -Encoding UTF8 -NoNewline

    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "reinstall succeeded (exit $exitCode)"
    Assert ((Get-Sha256 $exe) -eq $expected) "the executable was rebuilt by this build, not skipped"
    Assert ((Get-Content -LiteralPath $manifest -Raw) -match '"goldTargetSha256"') "the sidecar records the build that patched it"

    # ---------------------------------------------------------------- case 2
    # The same build over itself still changes nothing.
    Write-Host ""
    Write-Host "Case 2  reinstalling the same build over itself"
    $exe = New-Install "case2"
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "first patch succeeded (exit $exitCode)"
    $expected = Get-Sha256 $exe
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "second patch succeeded (exit $exitCode)"
    Assert ((Get-Sha256 $exe) -eq $expected) "the executable is unchanged"

    # ---------------------------------------------------------------- case 3
    # An executable this patcher does not know is still refused untouched.
    Write-Host ""
    Write-Host "Case 3  an unsupported executable is refused"
    $folder = Join-Path $WorkRoot "case3"
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $exe = Join-Path $folder "swkotor.exe"
    $bytes = [System.IO.File]::ReadAllBytes($CleanExe)
    $bytes[0x1000] = [byte](($bytes[0x1000] + 1) % 256)
    [System.IO.File]::WriteAllBytes($exe, $bytes)
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    $before = Get-Sha256 $exe
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -ne 0) "patching was refused (exit $exitCode)"
    Assert ((Get-Sha256 $exe) -eq $before) "the executable is untouched"

    # ---------------------------------------------------------------- case 4
    # A backup left behind by an interrupted run still blocks a patch, so a
    # damaged one is never mistaken for the clean build.
    Write-Host ""
    Write-Host "Case 4  a damaged backup blocks a fresh patch"
    $exe = New-Install "case4"
    Set-Content -LiteralPath ($exe + ".kotor-ui-backup") -Value "not the clean build" -Encoding ASCII
    $before = Get-Sha256 $exe
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -ne 0) "patching was refused (exit $exitCode)"
    Assert ((Get-Sha256 $exe) -eq $before) "the executable is untouched"
}
finally {
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
