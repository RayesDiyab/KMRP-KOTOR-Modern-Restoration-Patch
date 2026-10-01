<#
.SYNOPSIS
    Regression tests for the installer's update check.

.DESCRIPTION
    Compiles UpdateCheckSelfTest.cs together with the patcher source, so the test runs
    exactly the UpdateCheck code the patcher ships, then checks the release-tag parser,
    the version comparison, and the "Don't remind me again" round trip through
    %LOCALAPPDATA%\KMRP\settings.json, which it puts back byte for byte.

    -Live also asks GitHub once, as the patcher does, and prints the answer. It is
    informational: an offline machine is not a failure.

    -RenderTo draws the update dialog to a PNG at the given -Scale, as it looks in the
    patcher (the main window's scale; 1 is its 1080p design).

.EXAMPLE
    .\testing\regression\Test-UpdateCheck.ps1 -Live -RenderTo "$env:TEMP\update.png" -Scale 1.33
#>
[CmdletBinding()]
param(
    [switch]$Live,
    [string]$RenderTo,
    [double]$Scale = 1.0,
    [string]$WorkRoot
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-update-test-" + [guid]::NewGuid().ToString("N"))
}
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$harness = Join-Path $WorkRoot "UpdateCheckSelfTest.exe"

$compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
$sources = @(
    "src\patcher\KmrpPatcher.cs",
    "src\patcher\AbilityIconGenerator.cs",
    # KmrpPatcher.cs's Override step calls it since 2026-09-29.
    "src\patcher\GameArtGenerator.cs",
    "src\patcher\ControllerPromptGenerator.cs",
    "src\patcher\AssemblyInfo.cs",
    # KmrpPatcher.cs installs through it in either build since 2026-09-29.
    "src\patcher\KpmEdition.cs",
    "src\patcher\WindowsEnginePatch.cs",
    # The resolution list and the install blend sizes without a set since 2026-09-30.
    "src\patcher\GuiBlend.cs",
    "testing\regression\UpdateCheckSelfTest.cs"
) | ForEach-Object { Join-Path $projectRoot $_ }
$compilerArgs = @(
    "/nologo", "/target:exe", "/platform:anycpu", "/main:Kmrp.UpdateCheckSelfTest",
    "/out:$harness",
    "/reference:System.dll", "/reference:System.Drawing.dll",
    "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll",
    "/reference:System.Windows.Forms.dll"
) + $sources
& $compiler @compilerArgs
if ($LASTEXITCODE -ne 0) { throw "The self-test did not compile." }

$failed = $false
try {
    Write-Host "== tag parser, comparison, remembered version"
    & $harness
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    if ($RenderTo) {
        Write-Host "== the dialog"
        & $harness render $RenderTo ([string]::Format([Globalization.CultureInfo]::InvariantCulture, "{0}", $Scale))
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    }
    if ($Live) {
        Write-Host "== GitHub, once"
        & $harness live
    }
}
finally {
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failed) {
    Write-Host "FAILED" -ForegroundColor Red
    exit 1
}
