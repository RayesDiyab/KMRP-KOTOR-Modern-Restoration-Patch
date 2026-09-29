<#
.SYNOPSIS
    Regression test for installing KMRP over an earlier install of it.

.DESCRIPTION
    Since 2026-09-29 KMRP's installer runs KMRP on KOTOR Patch Manager's runtime and
    rewrites nothing in swkotor.exe but the large-address flag
    (src/patcher/KpmEdition.cs). Every KMRP installer before it -- KMRP 1.0 and
    the 1.5 builds up to that day -- wrote the gold delta into swkotor.exe and kept
    a backup of the original. So the upgrade that matters is from one of those:
    the new installer must restore the old install with the old install's own
    backups, and only then install.

    Case 1 installs with an earlier installer (-OlderPatcher, any KMRP installer
    from before 2026-09-29; the last standalone build, 061AD6A2..., is what this
    was written against) and requires the new one to replace it: the executable
    back to the original plus the flag, none of the old runtime left, and a
    restore that gives back the original. Case 4 requires a damaged old backup to
    refuse the upgrade and leave everything as it was. Cases 1 and 4 are skipped,
    and said so, without -OlderPatcher.

    Cases 2 and 3 pin what held before: the same build over itself changes
    nothing, and an unsupported executable is refused untouched. Case 5 is the
    old Case 4 turned around: a backup file left beside a clean executable
    blocked the standalone installer, which would have used it; the new one never
    reads it, so it installs and leaves it alone.

    Every check is made on the SHA-256 of the file.

    Until 2026-09-29 Case 1 simulated the older build by editing the installed
    executable and its sidecar, which is the shape the original bug was reported
    in: a sidecar truthful about a file this build did not produce, and the
    reinstall skipped.

.EXAMPLE
    .\testing\regression\Test-ReinstallOverOlderBuild.ps1 -OlderPatcher .\build\legacy\KMRP-standalone.exe
#>
[CmdletBinding()]
param(
    [string]$Patcher      = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$OlderPatcher = ".\build\legacy\KMRP-standalone.exe",
    [string]$CleanExe     = ".\build-inputs\swkotornopatch.exe",
    [string]$SeedIni      = ".\testing\virtual-display\swkotor-7680-windowed.ini",
    [string]$Resolution   = "1920x1080",
    [string]$WorkRoot,
    [switch]$KeepWorkRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Restore-TestNvidiaProfiles.ps1")
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Resolve-Input([string]$path) {
    if ([System.IO.Path]::IsPathRooted($path)) { return $path }
    return (Join-Path $projectRoot $path)
}

$Patcher      = Resolve-Input $Patcher
$OlderPatcher = Resolve-Input $OlderPatcher
$CleanExe     = Resolve-Input $CleanExe
$SeedIni      = Resolve-Input $SeedIni

foreach ($required in @($Patcher, $CleanExe, $SeedIni)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required input is missing: $required"
    }
}
$haveOlder = Test-Path -LiteralPath $OlderPatcher

if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-reinstall-" + [Guid]::NewGuid().ToString("N"))
}

$script:Failures = 0
$layersPath = "Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
$script:OriginalLayerValues = @{}
$laaHash = "CA9D22EACB5BDFA8E2AD3F8935B0E8E2FED72DA8132D0622D576A650AA7E1889"

function Get-LayerValue([string]$exePath) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($layersPath, $false)
    try {
        if ($null -eq $key -or $key.GetValueNames() -notcontains $exePath) {
            return [pscustomobject]@{ Exists = $false; Value = $null }
        }
        return [pscustomobject]@{
            Exists = $true
            Value = [string]$key.GetValue($exePath, $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        }
    }
    finally {
        if ($null -ne $key) { $key.Dispose() }
    }
}

function Restore-LayerValue([string]$exePath, $saved) {
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($layersPath)
    try {
        if ($saved.Exists) {
            $key.SetValue($exePath, $saved.Value, [Microsoft.Win32.RegistryValueKind]::String)
        } else {
            $key.DeleteValue($exePath, $false)
        }
    }
    finally {
        $key.Dispose()
    }
}

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
function Invoke-Exe([string]$exe, [string[]]$patcherArgs) {
    $process = Start-Process -FilePath $exe -ArgumentList $patcherArgs -Wait -PassThru -NoNewWindow
    return $process.ExitCode
}
function Invoke-Patcher([string[]]$patcherArgs) { return Invoke-Exe $Patcher $patcherArgs }

# A throwaway game folder: the executable, the swkotor.ini the installer requires, and
# a stand-in binkw32.dll, which the installer renames for KOTOR Patch Manager's proxy
# and puts back.
function New-Install([string]$name, [string]$source = $CleanExe) {
    $folder = Join-Path $WorkRoot $name
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $exe = Join-Path $folder "kmrp-regression-selftest.exe"
    Copy-Item -LiteralPath $source -Destination $exe
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    [System.IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
    $script:OriginalLayerValues[$exe] = Get-LayerValue $exe
    return $exe
}

# Refusals write KMRP.startup-error.log beside each installer, which would then ship
# from dist\. Those this run creates are removed at the end.
$errorLogs = @($Patcher, $OlderPatcher | ForEach-Object { Join-Path (Split-Path -Parent $_) "KMRP.startup-error.log" })
$errorLogsBefore = @($errorLogs | Where-Object { Test-Path -LiteralPath $_ })
$cleanHash = Get-Sha256 $CleanExe

New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
Write-Host ""
Write-Host ("Reinstall regression  ->  " + $WorkRoot)
Write-Host ("resolution " + $Resolution)

try {
    # ---------------------------------------------------------------- case 1
    Write-Host ""
    Write-Host "Case 1  installing over an earlier KMRP, which patched swkotor.exe"
    if (-not $haveOlder) {
        Write-Host "  SKIPPED  no earlier installer at $OlderPatcher; pass -OlderPatcher" -ForegroundColor DarkYellow
    } else {
        $exe = New-Install "case1"
        $folder = Split-Path -Parent $exe
        $standIn = Get-Sha256 (Join-Path $folder "binkw32.dll")
        Assert ((Invoke-Exe $OlderPatcher @("--in-place", $exe, $Resolution)) -eq 0) "the earlier installer installs"
        $gold = Get-Sha256 $exe
        Assert ($gold -ne $cleanHash -and $gold -ne $laaHash) "it rewrote swkotor.exe"
        $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
        Assert ($exitCode -eq 0) "this build installs over it (exit $exitCode)"
        Assert ((Get-Sha256 $exe) -eq $laaHash) "swkotor.exe is the original plus the large-address flag"
        foreach ($name in @("kmrp-controller-runtime.asi", "kmrp-controller.module", "KMRP_Controller.manifest")) {
            Assert (-not (Test-Path -LiteralPath (Join-Path $folder $name))) ("the earlier runtime's " + $name + " is gone")
        }
        foreach ($name in @("KMRP_KPM.manifest", "KotorPatcher.dll", "patch_config.toml", "binkw32Hooked.dll")) {
            Assert (Test-Path -LiteralPath (Join-Path $folder $name)) ("this build installed " + $name)
        }
        $sidecar = [System.IO.File]::ReadAllText($exe + ".kotor-ui-patch.json")
        Assert ($sidecar -match '"state"\s*:\s*"restored"') "the earlier install's record says it was restored"
        Assert ((Invoke-Patcher @("--restore", $exe)) -eq 0) "restore succeeds"
        Assert ((Get-Sha256 $exe) -eq $cleanHash) "swkotor.exe is the original, byte for byte"
        Assert ((Get-Sha256 (Join-Path $folder "binkw32.dll")) -eq $standIn) "binkw32.dll is the game's"
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KotorPatcher.dll"))) "the runtime is gone"
    }

    # ---------------------------------------------------------------- case 2
    Write-Host ""
    Write-Host "Case 2  reinstalling the same build over itself"
    $exe = New-Install "case2"
    $folder = Split-Path -Parent $exe
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "first install succeeded (exit $exitCode)"
    $before = @{}
    foreach ($name in @("kmrp-kpm.dat", "patch_config.toml", "KotorPatcher.dll", "binkw32.dll", "binkw32Hooked.dll")) {
        $before[$name] = Get-Sha256 (Join-Path $folder $name)
    }
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "second install succeeded (exit $exitCode)"
    Assert ((Get-Sha256 $exe) -eq $laaHash) "the executable is unchanged"
    foreach ($name in $before.Keys) {
        Assert ((Get-Sha256 (Join-Path $folder $name)) -eq $before[$name]) ($name + " is unchanged")
    }
    Assert ((Invoke-Patcher @("--restore", $exe)) -eq 0) "restore succeeds"
    Assert ((Get-Sha256 $exe) -eq $cleanHash) "swkotor.exe is the original"

    # ---------------------------------------------------------------- case 3
    # An executable this installer does not know is still refused untouched.
    Write-Host ""
    Write-Host "Case 3  an unsupported executable is refused"
    $folder = Join-Path $WorkRoot "case3"
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $exe = Join-Path $folder "kmrp-regression-selftest.exe"
    $stream = [System.IO.File]::Open($exe, [System.IO.FileMode]::Create)
    try { $source = [System.IO.File]::OpenRead($CleanExe); try { $source.CopyTo($stream) } finally { $source.Dispose() }
          $stream.Position = 0x1000; $value = $stream.ReadByte(); $stream.Position = 0x1000; $stream.WriteByte(($value + 1) % 256) }
    finally { $stream.Dispose() }
    Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
    [System.IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
    $script:OriginalLayerValues[$exe] = Get-LayerValue $exe
    $before = Get-Sha256 $exe
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -ne 0) "installing was refused (exit $exitCode)"
    Assert ((Get-Sha256 $exe) -eq $before) "the executable is untouched"
    Assert (-not (Test-Path -LiteralPath (Join-Path $folder "binkw32Hooked.dll"))) "binkw32.dll is untouched"

    # ---------------------------------------------------------------- case 4
    Write-Host ""
    Write-Host "Case 4  an earlier KMRP with a damaged backup is not replaced"
    if (-not $haveOlder) {
        Write-Host "  SKIPPED  no earlier installer at $OlderPatcher; pass -OlderPatcher" -ForegroundColor DarkYellow
    } else {
        $exe = New-Install "case4"
        $folder = Split-Path -Parent $exe
        Assert ((Invoke-Exe $OlderPatcher @("--in-place", $exe, $Resolution)) -eq 0) "the earlier installer installs"
        Set-Content -LiteralPath ($exe + ".kotor-ui-backup") -Value "not the clean build" -Encoding ASCII
        $before = Get-Sha256 $exe
        $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
        Assert ($exitCode -ne 0) "installing was refused (exit $exitCode)"
        Assert ((Get-Sha256 $exe) -eq $before) "the executable is untouched"
        Assert (Test-Path -LiteralPath (Join-Path $folder "KMRP_Controller.manifest")) "the earlier install is left as it was"
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KMRP_KPM.manifest"))) "nothing of this build was installed"
    }

    # ---------------------------------------------------------------- case 5
    Write-Host ""
    Write-Host "Case 5  a backup left beside a clean executable does not block the install"
    $exe = New-Install "case5"
    $stray = $exe + ".kotor-ui-backup"
    Set-Content -LiteralPath $stray -Value "not the clean build" -Encoding ASCII
    $strayHash = Get-Sha256 $stray
    $exitCode = Invoke-Patcher @("--in-place", $exe, $Resolution)
    Assert ($exitCode -eq 0) "the install succeeded (exit $exitCode)"
    Assert ((Get-Sha256 $stray) -eq $strayHash) "the stray backup is left alone"
    Assert ((Invoke-Patcher @("--restore", $exe)) -eq 0) "restore succeeds"
    Assert ((Get-Sha256 $exe) -eq $cleanHash) "swkotor.exe is the original"
}
finally {
    foreach ($log in $errorLogs) {
        if ((Test-Path -LiteralPath $log) -and $errorLogsBefore -notcontains $log) { Remove-Item -LiteralPath $log -Force }
    }
    Restore-TestNvidiaProfiles $WorkRoot
    foreach ($entry in $script:OriginalLayerValues.GetEnumerator()) {
        Restore-LayerValue $entry.Key $entry.Value
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
