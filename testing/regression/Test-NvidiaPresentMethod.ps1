<#
.SYNOPSIS
    Regression tests for the patcher's removal of the NVIDIA present method older KMRP
    installs set.

.DESCRIPTION
    Since 2026-10-30 KMRP sets no NVIDIA "Vulkan/OpenGL present method": its module
    draws each frame offscreen (K1OffscreenFrame.cpp), so NVIDIA's layered path no longer
    shows half-drawn frames. Every install and restore removes the Prefer native that KMRP
    set from 2026-09-19, while KMRP's record of it exists and the game's profile still
    holds it (NvidiaPresentOperations.Restore).

    Compiles NvidiaPresentSelfTest.cs together with the patcher source, so the test runs
    exactly the code the patcher ships, then:

      1. describes what NVIDIA applies to the game executable given (read-only);
      2. on a throwaway executable named kmrp-nvapi-selftest.exe, plants what an older
         install left and checks Restore: KMRP's own profile removed; KMRP's value removed
         from an existing profile; a value the player changed since left; a profile that
         became shared kept; Prefer native with no record left; a profile with KMRP's name
         that does not hold the game left.

    No real game's profile is written: NVIDIA matches profiles by executable name, and
    the throwaway name matches nothing. Every profile the test creates is removed in a
    finally block, and the global profile is only read. Without an NVIDIA driver it
    reports SKIP and exits 0.

.EXAMPLE
    .\testing\regression\Test-NvidiaPresentMethod.ps1 -GameExe "C:\Star Wars - KotOR\swkotor.exe"
#>
[CmdletBinding()]
param(
    [string]$GameExe,
    [string]$WorkRoot
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $WorkRoot) {
    $WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("kmrp-nvapi-test-" + [guid]::NewGuid().ToString("N"))
}
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null
$harness = Join-Path $WorkRoot "NvidiaPresentSelfTest.exe"

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
    "testing\regression\NvidiaPresentSelfTest.cs"
) | ForEach-Object { Join-Path $projectRoot $_ }
$compilerArgs = @(
    "/nologo", "/target:exe", "/platform:anycpu", "/main:Kmrp.NvidiaPresentSelfTest",
    "/out:$harness",
    "/reference:System.dll", "/reference:System.Drawing.dll",
    "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll",
    "/reference:System.Windows.Forms.dll"
) + $sources
& $compiler @compilerArgs
if ($LASTEXITCODE -ne 0) { throw "The self-test did not compile." }

$failed = $false
try {
    if ($GameExe) {
        Write-Host "== what NVIDIA applies to $GameExe"
        & $harness describe $GameExe
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    }
    Write-Host "== restore of what older installs left, on a throwaway executable"
    & $harness cycle (Join-Path $WorkRoot "cycle")
    switch ($LASTEXITCODE) {
        0 { }
        2 { Write-Host "SKIP: no NVIDIA driver." }
        3 { Write-Host "BLOCKED: see above."; $failed = $true }
        default { $failed = $true }
    }
}
finally {
    Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($failed) {
    Write-Host "FAILED" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED" -ForegroundColor Green
exit 0
