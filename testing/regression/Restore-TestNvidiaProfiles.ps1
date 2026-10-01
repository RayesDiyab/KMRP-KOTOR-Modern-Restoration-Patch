# Dot-sourced by installer regressions. NVIDIA profiles match basenames across
# directories; fixtures use a distinct basename and must undo their DRS records
# before deleting the temporary directory, including damaged-backup test cases.
function Restore-TestNvidiaProfiles([string]$FixtureRoot) {
    $fixturePath = [IO.Path]::GetFullPath($FixtureRoot)
    $records = @(Get-ChildItem -LiteralPath $fixturePath -Filter KMRP_NVIDIA.manifest -Recurse -File)
    if (-not $records.Count) { return }
    $projectPath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $harnessPath = Join-Path $fixturePath 'NvidiaRegressionCleanup.exe'
    $sourcePaths = @(
        'src/patcher/KmrpPatcher.cs', 'src/patcher/AbilityIconGenerator.cs',
        'src/patcher/GameArtGenerator.cs',
        'src/patcher/ControllerPromptGenerator.cs', 'src/patcher/AssemblyInfo.cs',
        'src/patcher/KpmEdition.cs', 'src/patcher/WindowsEnginePatch.cs', 'src/patcher/GuiBlend.cs',
        'testing/regression/NvidiaPresentSelfTest.cs'
    ) | ForEach-Object { Join-Path $projectPath $_ }
    & 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe' /nologo /target:exe /platform:anycpu /main:Kmrp.NvidiaPresentSelfTest "/out:$harnessPath" /reference:System.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Windows.Forms.dll @sourcePaths
    if ($LASTEXITCODE -ne 0) { throw 'NVIDIA fixture cleanup did not compile; preserving fixtures.' }
    foreach ($record in $records) {
        $lines = [IO.File]::ReadAllLines($record.FullName)
        if ($lines.Length -ne 3) { throw 'Unexpected NVIDIA fixture record; preserving fixtures.' }
        $exePath = [IO.Path]::GetFullPath([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($lines[1])))
        if ([IO.Path]::GetDirectoryName($exePath) -ne $record.DirectoryName -or
            [IO.Path]::GetFileName($exePath) -notin @('kmrp-regression-selftest.exe', 'kmrp-controller-selftest.exe', 'kmrp-kpm-selftest.exe')) {
            throw 'Refusing NVIDIA cleanup for an executable outside these fixtures.'
        }
        & $harnessPath restore $exePath
        if ($LASTEXITCODE -ne 0) { throw 'NVIDIA fixture cleanup failed; preserving recovery record.' }
    }
}

# The other per-user state a fixture install leaves outside its folder: the Windows
# high-DPI value (HKCU\...\AppCompatFlags\Layers, HIGHDPIAWARE), keyed by the fixture
# executable's full path. Only that fixture's own --restore removes it, so a run that
# stops between install and restore -- a failed assertion, an exception, an
# interrupt -- deleted the folder and orphaned the value. Twelve were found on
# 2026-09-25, two from Test-ControllerSupport's current fixtures.
#
# Removes every value under this run's fixture root that names a fixture executable,
# and nothing else: both conditions, so an unusual -WorkRoot can never reach a real
# game's entry. Called only when the run deletes its folder: with -KeepWorkRoot the
# fixtures stay installed on purpose, and --restore on each removes its value.
#
# The installer itself is not at fault: a completed install is meant to keep its
# value until Restore Original (docs/windows-dpi-scaling.md).
function Remove-TestDpiValues([string]$FixtureRoot) {
    $root = [IO.Path]::GetFullPath($FixtureRoot).TrimEnd('\') + '\'
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(
        'Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers', $true)
    if ($null -eq $key) { return }
    try {
        foreach ($name in $key.GetValueNames()) {
            if ($name.StartsWith($root, [StringComparison]::OrdinalIgnoreCase) -and
                [IO.Path]::GetFileName($name) -in @('kmrp-regression-selftest.exe', 'kmrp-controller-selftest.exe')) {
                $key.DeleteValue($name, $false)
            }
        }
    }
    finally {
        $key.Dispose()
    }
}

# Since 2026-09-29 an install also puts KMRP's .kpatch files into KOTOR Patch
# Manager's patch folder when KPM's own settings name one (KpmEditionOperations
# .DeliverKpatches). A test run must never write into a player's real KPM folder,
# so the six suites that install move KPM's settings into their work folder for the
# run -- a copy on disk, which survives the script being stopped -- and put them
# back first thing in their `finally`. A settings file a test wrote itself is
# removed then.
function Get-KpmLauncherSettingsPath {
    Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::ApplicationData)) 'KPatchLauncher\settings.json'
}

function Hide-KpmLauncherSettings([string]$FixtureRoot) {
    $settings = Get-KpmLauncherSettingsPath
    if (-not (Test-Path -LiteralPath $settings)) { return $null }
    $parked = Join-Path $FixtureRoot 'kpm-launcher-settings.json'
    Move-Item -LiteralPath $settings -Destination $parked -Force
    return $parked
}

function Restore-KpmLauncherSettings([string]$Parked) {
    $settings = Get-KpmLauncherSettingsPath
    if (Test-Path -LiteralPath $settings) { Remove-Item -LiteralPath $settings -Force }
    if ($Parked -and (Test-Path -LiteralPath $Parked)) {
        Move-Item -LiteralPath $Parked -Destination $settings -Force
    }
    elseif ((Test-Path -LiteralPath (Split-Path -Parent $settings)) -and
            @(Get-ChildItem -LiteralPath (Split-Path -Parent $settings) -Force).Count -eq 0) {
        # The folder a test made for its own settings file, when KPM had none.
        Remove-Item -LiteralPath (Split-Path -Parent $settings) -Force
    }
}
