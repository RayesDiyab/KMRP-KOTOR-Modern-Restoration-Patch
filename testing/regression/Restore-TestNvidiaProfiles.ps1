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
        'src/patcher/ControllerPromptGenerator.cs', 'src/patcher/AssemblyInfo.cs',
        'testing/regression/NvidiaPresentSelfTest.cs'
    ) | ForEach-Object { Join-Path $projectPath $_ }
    & 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe' /nologo /target:exe /platform:anycpu /main:Kmrp.NvidiaPresentSelfTest "/out:$harnessPath" /reference:System.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Windows.Forms.dll @sourcePaths
    if ($LASTEXITCODE -ne 0) { throw 'NVIDIA fixture cleanup did not compile; preserving fixtures.' }
    foreach ($record in $records) {
        $lines = [IO.File]::ReadAllLines($record.FullName)
        if ($lines.Length -ne 3) { throw 'Unexpected NVIDIA fixture record; preserving fixtures.' }
        $exePath = [IO.Path]::GetFullPath([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($lines[1])))
        if ([IO.Path]::GetDirectoryName($exePath) -ne $record.DirectoryName -or
            [IO.Path]::GetFileName($exePath) -notin @('kmrp-regression-selftest.exe', 'kmrp-controller-selftest.exe')) {
            throw 'Refusing NVIDIA cleanup for an executable outside these fixtures.'
        }
        & $harnessPath restore $exePath
        if ($LASTEXITCODE -ne 0) { throw 'NVIDIA fixture cleanup failed; preserving recovery record.' }
    }
}
