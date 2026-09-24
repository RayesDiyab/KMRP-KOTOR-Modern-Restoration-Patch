<#
.SYNOPSIS
    Regression tests for the patcher's NVIDIA "Vulkan/OpenGL present method" step.

.DESCRIPTION
    Compiles NvidiaPresentSelfTest.cs together with the patcher source, so the test
    runs exactly the NvidiaPresentOperations code the patcher ships, then:

      1. describes what NVIDIA applies to the game executable given (read-only);
      2. runs install -> verify -> restore -> verify three ways, on a throwaway
         executable named kmrp-nvapi-selftest.exe: with no profile naming it, with a
         stand-in profile that inherits the setting, and with one that holds Prefer
         layered deliberately.

    No real game's profile is written: NVIDIA matches profiles by executable name, and
    the throwaway name matches nothing. Every profile the test creates is removed in
    a finally block, and the global profile is only read.

    The cycle needs an NVIDIA driver whose global present method is "Prefer layered
    on DXGI Swapchain" -- the only state in which the patcher changes anything. On any
    other machine it reports SKIP and exits 0.

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
    "src\patcher\ControllerPromptGenerator.cs",
    "src\patcher\AssemblyInfo.cs",
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
    Write-Host "== install / restore cycles on a throwaway executable"
    & $harness cycle (Join-Path $WorkRoot "cycle")
    switch ($LASTEXITCODE) {
        0 { }
        2 { Write-Host "SKIP: no NVIDIA driver, or its global present method is not Prefer layered." }
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
