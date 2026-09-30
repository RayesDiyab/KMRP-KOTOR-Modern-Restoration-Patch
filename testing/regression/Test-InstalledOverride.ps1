<#
.SYNOPSIS
    The Override files an install writes must be the build's archives, exactly.

.DESCRIPTION
    The Python regression checks read the build's archives in build\kmrp\resources:
    override-common.zip, and one gui-<W>x<H>.zip per resolution. Since 2026-09-25
    the installer does not embed those per-resolution archives. It embeds one pool
    that stores each distinct file once (tools/pack_resolution_layouts.py), and
    rebuilds the chosen resolution's files from it. The packer checks the pool
    against the archives when it builds it; this checks what the installer writes.

    For each resolution: patch a throwaway fixture in place, then require its
    Override folder to hold exactly the files of override-common.zip and that
    resolution's archive -- the same names, and the same SHA-256 for each -- less
    kmrp_prompts.txt, which the installer reads and does not install. A fixture has
    no dialog.tlk, no texture pack and no chitin.key, so no prompt badge is moved,
    no ability icon is generated, and neither are the row frames, tutorial icons and
    tutorial.2da (GameArtGenerator, 2026-09-29; Test-GameArt.py covers those): every
    file must match its archive byte for byte. Then
    restore, and require the Override folder to be empty again.

    It passes on an installer from before the pool as well, which embedded the
    archives themselves. A failure means the installer and the resource folder are
    not from the same build, or the installer rebuilt a layout wrongly.

    Sizes the build has no set for (-Blended, 2026-09-30) install the nearest set --
    the nearest height, then the nearest shape, as the Mac installer picks it -- with
    its .gui files, controller badges and HUD button-row boxes replaced by the ones made
    for the size (src/patcher/GuiBlend.cs). For those, each of these must be what the
    installer's --derive-gui makes from build\kmrp\gui-blend.bin with that set's fonts,
    and every other file the set's own; swkotor.ini must hold the size.
    Test-GuiBlendHelper.py proves that blend equals the Mac's, byte for byte.

.EXAMPLE
    .\testing\regression\Test-InstalledOverride.ps1

.EXAMPLE
    .\testing\regression\Test-InstalledOverride.ps1 -Resolutions all
#>
[CmdletBinding()]
param(
    [string]$Patcher   = ".\dist\KMRP - KOTOR Modern Restoration Patch.exe",
    [string]$CleanExe  = ".\build-inputs\swkotornopatch.exe",
    [string]$SeedIni   = ".\testing\virtual-display\swkotor-7680-windowed.ini",
    [string]$Resources = ".\build\kmrp\resources",
    # 3440x1440 is built from the gold GUI files, 2880x1620 is derived from
    # 2560x1440, and 1920x1080 and 800x600 are upstream layouts of two aspects.
    # "all" installs every archive in -Resources, 49 installs.
    [string[]]$Resolutions = @("3440x1440", "2880x1620", "1920x1080", "800x600"),
    # No set: between 16:9 and 21:9 at a 16:10 set's height, a 16:10 shape between
    # two heights, and a 21:9 shape between two heights.
    [string[]]$Blended = @("2560x1200", "1600x1000", "3440x1400"),
    [string]$BlendTable = ".\build\kmrp\gui-blend.bin",
    [string]$WorkRoot,
    [switch]$KeepWorkRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "Restore-TestNvidiaProfiles.ps1")
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Resolve-Input([string]$path) {
    if ([System.IO.Path]::IsPathRooted($path)) { return $path }
    return (Join-Path $projectRoot $path)
}

$Patcher   = Resolve-Input $Patcher
$CleanExe  = Resolve-Input $CleanExe
$SeedIni   = Resolve-Input $SeedIni
$Resources = Resolve-Input $Resources
$BlendTable = Resolve-Input $BlendTable

foreach ($required in @($Patcher, $CleanExe, $SeedIni, (Join-Path $Resources "override-common.zip"))) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required input is missing: $required"
    }
}
if ($Resolutions.Count -eq 1 -and $Resolutions[0] -eq "all") {
    $Resolutions = @(Get-ChildItem -LiteralPath $Resources -Filter "gui-*.zip" |
        Sort-Object Name | ForEach-Object { $_.BaseName.Substring(4) })
}

if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-override-" + [Guid]::NewGuid().ToString("N"))
}

$script:Failures = 0
$layersPath = "Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
$script:OriginalLayerValues = @{}

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

function Get-StreamHash($sha, $stream) {
    return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace("-", "")
}

# Lower-case Override name -> SHA-256 for every file in the archives, as the
# installer names them: "/" becomes "\". kmrp_prompts.txt is build metadata the
# installer reads and does not install.
function Get-ExpectedFiles([string[]]$archives) {
    $expected = @{}
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        foreach ($archive in $archives) {
            $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
            try {
                foreach ($entry in $zip.Entries) {
                    if (-not $entry.Name) { continue }
                    $name = $entry.FullName.Replace("/", "\").ToLowerInvariant()
                    if ($name -eq "kmrp_prompts.txt") { continue }
                    $stream = $entry.Open()
                    try { $hash = Get-StreamHash $sha $stream } finally { $stream.Dispose() }
                    if ($expected.ContainsKey($name) -and $expected[$name] -ne $hash) {
                        throw "Two archives disagree about $name"
                    }
                    $expected[$name] = $hash
                }
            }
            finally {
                $zip.Dispose()
            }
        }
    }
    finally {
        $sha.Dispose()
    }
    return $expected
}

function Get-InstalledFiles([string]$override) {
    $installed = @{}
    if (-not (Test-Path -LiteralPath $override)) { return $installed }
    $root = [System.IO.Path]::GetFullPath($override).TrimEnd("\") + "\"
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        foreach ($file in Get-ChildItem -LiteralPath $override -Recurse -File -Force) {
            $stream = [System.IO.File]::OpenRead($file.FullName)
            try { $hash = Get-StreamHash $sha $stream } finally { $stream.Dispose() }
            $installed[$file.FullName.Substring($root.Length).ToLowerInvariant()] = $hash
        }
    }
    finally {
        $sha.Dispose()
    }
    return $installed
}

function Show-Examples([string]$label, [string[]]$names) {
    foreach ($name in @($names | Sort-Object | Select-Object -First 5)) {
        Write-Host ("        {0}: {1}" -f $label, $name) -ForegroundColor Red
    }
}

New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
Write-Host ""
Write-Host ("Installed Override regression  ->  " + $WorkRoot)
Write-Host ("installer " + (Split-Path -Leaf $Patcher))
Write-Host ("resolutions " + ($Resolutions -join ", "))

$common = Join-Path $Resources "override-common.zip"
# KPM's own settings, parked for the run (Restore-TestNvidiaProfiles.ps1).
$kpmLauncherSettings = Hide-KpmLauncherSettings $WorkRoot
try {
    foreach ($resolution in $Resolutions) {
        Write-Host ""
        Write-Host ("Resolution " + $resolution)
        $archive = Join-Path $Resources ("gui-" + $resolution + ".zip")
        if (-not (Test-Path -LiteralPath $archive)) {
            Assert $false "the build has an archive for $resolution"
            continue
        }
        $expected = Get-ExpectedFiles @($common, $archive)

        $folder = Join-Path $WorkRoot $resolution
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        $exe = Join-Path $folder "kmrp-regression-selftest.exe"
        Copy-Item -LiteralPath $CleanExe -Destination $exe
        Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
        # KMRP's installer renames the game's binkw32.dll to put KOTOR Patch Manager's
        # proxy in its place, and puts it back on restore; any bytes stand in for it.
        [IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
        $script:OriginalLayerValues[$exe] = Get-LayerValue $exe
        $override = Join-Path $folder "Override"

        $exitCode = Invoke-Patcher @("--in-place", $exe, $resolution)
        Assert ($exitCode -eq 0) "patch succeeded (exit $exitCode)"
        $installed = Get-InstalledFiles $override

        $missing = @($expected.Keys | Where-Object { -not $installed.ContainsKey($_) })
        $extra = @($installed.Keys | Where-Object { -not $expected.ContainsKey($_) })
        $different = @($expected.Keys | Where-Object {
            $installed.ContainsKey($_) -and $installed[$_] -ne $expected[$_] })
        Assert ($missing.Count -eq 0) ("every archive file was installed ({0} of {1})" -f
            ($expected.Count - $missing.Count), $expected.Count)
        Show-Examples "missing" $missing
        Assert ($extra.Count -eq 0) ("nothing else was installed ({0} extra)" -f $extra.Count)
        Show-Examples "extra" $extra
        Assert ($different.Count -eq 0) ("every installed file matches its archive byte for byte ({0} differ)" -f
            $different.Count)
        Show-Examples "differs" $different

        $exitCode = Invoke-Patcher @("--restore", $exe)
        Assert ($exitCode -eq 0) "restore succeeded (exit $exitCode)"
        $left = Get-InstalledFiles $override
        Assert ($left.Count -eq 0) ("restore emptied Override ({0} left)" -f $left.Count)
        Assert (-not (Test-Path -LiteralPath (Join-Path $folder "KOTOR_UI_Override_Backup.manifest"))) `
            "restore removed the Override manifest"
    }

    # Start-Process splits arguments at spaces, and the project folder's name has them: the
    # table goes to the work folder first.
    $tableCopy = Join-Path $WorkRoot "gui-blend.bin"
    Copy-Item -LiteralPath $BlendTable -Destination $tableCopy
    # The listed sizes, as the installer lists them, for the nearest set.
    $listed = @(Get-Content -LiteralPath (Join-Path $Resources "resolutions.tsv") |
        Where-Object { $_ -and -not $_.StartsWith("#") } |
        ForEach-Object { $f = $_.Split("`t"); [pscustomobject]@{ Key = "$($f[1])x$($f[2])"; W = [int]$f[1]; H = [int]$f[2] } })
    foreach ($resolution in $Blended) {
        Write-Host ""
        Write-Host ("Resolution " + $resolution + ", no set: blended")
        $w, $h = $resolution.Split("x") | ForEach-Object { [int]$_ }
        Assert (-not ($listed | Where-Object { $_.Key -eq $resolution })) "the build has no set for $resolution"
        $near = $null
        foreach ($candidate in $listed) {
            $dh = [Math]::Abs($candidate.H - $h)
            $da = [Math]::Abs($candidate.W / $candidate.H - $w / $h)
            if ($null -eq $near -or $dh -lt $nearDh -or ($dh -eq $nearDh -and $da -lt $nearDa)) {
                $near = $candidate; $nearDh = $dh; $nearDa = $da
            }
        }
        Write-Host ("  nearest set " + $near.Key)
        $archive = Join-Path $Resources ("gui-" + $near.Key + ".zip")
        $expected = Get-ExpectedFiles @($common, $archive)

        # The blend, with the nearest set's two files it reads.
        $setDir = Join-Path $WorkRoot ("set-" + $near.Key)
        $blendDir = Join-Path $WorkRoot ("blend-" + $resolution)
        New-Item -ItemType Directory -Force -Path $setDir | Out-Null
        $zip = [System.IO.Compression.ZipFile]::OpenRead($archive)
        try {
            foreach ($name in @("kmrp_prompts.txt", "dialogfont16x16.txi")) {
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($zip.GetEntry($name), (Join-Path $setDir $name), $true)
            }
        }
        finally { $zip.Dispose() }
        $exitCode = Invoke-Patcher @("--derive-gui", $tableCopy, "$w", "$h", $blendDir, $setDir)
        Assert ($exitCode -eq 0) "the installer's blend writes the menus (exit $exitCode)"
        # Every file the blend makes but the manifest, which the installer reads and does
        # not install: the menus, the badges drawn for the blended buttons, the HUD boxes.
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $madeGui = 0; $madeBadges = 0
        try {
            foreach ($file in Get-ChildItem -LiteralPath $blendDir -File) {
                $name = $file.Name.ToLowerInvariant()
                if ($name -eq "kmrp_prompts.txt") { continue }
                $stream = [System.IO.File]::OpenRead($file.FullName)
                try { $hash = Get-StreamHash $sha $stream } finally { $stream.Dispose() }
                Assert ($expected.ContainsKey($name)) "the nearest set has $name, which the blend makes"
                if ($expected[$name] -ne $hash) {
                    if ($name.EndsWith(".gui")) { $madeGui++ } elseif ($name.StartsWith("kmr")) { $madeBadges++ }
                }
                $expected[$name] = $hash
            }
        }
        finally { $sha.Dispose() }
        Assert ($madeGui -gt 60 -and $madeBadges -gt 400) ("the blend differs from the nearest set's menus and badges ({0} .gui files, {1} badges)" -f $madeGui, $madeBadges)

        $folder = Join-Path $WorkRoot $resolution
        New-Item -ItemType Directory -Force -Path $folder | Out-Null
        $exe = Join-Path $folder "kmrp-regression-selftest.exe"
        Copy-Item -LiteralPath $CleanExe -Destination $exe
        Copy-Item -LiteralPath $SeedIni -Destination (Join-Path $folder "swkotor.ini")
        [IO.File]::WriteAllText((Join-Path $folder "binkw32.dll"), "stand-in for the game's binkw32.dll`r`n")
        $script:OriginalLayerValues[$exe] = Get-LayerValue $exe
        $override = Join-Path $folder "Override"

        $exitCode = Invoke-Patcher @("--in-place", $exe, $resolution)
        Assert ($exitCode -eq 0) "patch succeeded (exit $exitCode)"
        $installed = Get-InstalledFiles $override
        $missing = @($expected.Keys | Where-Object { -not $installed.ContainsKey($_) })
        $extra = @($installed.Keys | Where-Object { -not $expected.ContainsKey($_) })
        $different = @($expected.Keys | Where-Object {
            $installed.ContainsKey($_) -and $installed[$_] -ne $expected[$_] })
        Assert ($missing.Count -eq 0 -and $extra.Count -eq 0) ("the nearest set's files were installed, nothing else ({0} missing, {1} extra)" -f
            $missing.Count, $extra.Count)
        Show-Examples "missing" $missing
        Show-Examples "extra" $extra
        Assert ($different.Count -eq 0) ("every .gui is the blend and every other file the set's, byte for byte ({0} differ)" -f
            $different.Count)
        Show-Examples "differs" $different
        $ini = [IO.File]::ReadAllText((Join-Path $folder "swkotor.ini"))
        Assert (($ini -match "(?m)^Width=$w\r?$") -and ($ini -match "(?m)^Height=$h\r?$")) "swkotor.ini holds $resolution"

        $exitCode = Invoke-Patcher @("--restore", $exe)
        Assert ($exitCode -eq 0) "restore succeeded (exit $exitCode)"
        $left = Get-InstalledFiles $override
        Assert ($left.Count -eq 0) ("restore emptied Override ({0} left)" -f $left.Count)
    }
}
finally {
    Restore-KpmLauncherSettings $kpmLauncherSettings
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
