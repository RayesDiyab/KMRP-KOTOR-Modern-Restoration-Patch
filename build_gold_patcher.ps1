param(
    [string]$SourceExe = "..\swkotornopatch.exe",
    [string]$GoldExe = "..\swkotor_gold_final_D8F0EEBF.exe",
    [string]$OverrideSource = ".\assets\override-3440x1440",
    [string]$IconPath = ".\app\patcher\favicon.ico"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $projectRoot "build\gold-patcher"
$distDir = Join-Path $projectRoot "dist"
$patchResource = Join-Path $buildDir "gold.kup"
$overrideResource = Join-Path $buildDir "override-3440x1440.zip"
$outputExe = Join-Path $distDir "KOTOR_UI_Gold_Patcher.exe"
$python = "C:\Python314\python.exe"
$compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python was not found at $python"
}
if (-not (Test-Path -LiteralPath $compiler)) {
    throw ".NET Framework C# compiler was not found at $compiler"
}

$resolvedSource = (Resolve-Path -LiteralPath (Join-Path $projectRoot $SourceExe)).Path
$resolvedGold = (Resolve-Path -LiteralPath (Join-Path $projectRoot $GoldExe)).Path
$overrideCandidate = if ([IO.Path]::IsPathRooted($OverrideSource)) {
    $OverrideSource
} else {
    Join-Path $projectRoot $OverrideSource
}
$resolvedOverride = (Resolve-Path -LiteralPath $overrideCandidate).Path
$resolvedIcon = (Resolve-Path -LiteralPath (Join-Path $projectRoot $IconPath)).Path
New-Item -ItemType Directory -Force -Path $buildDir, $distDir | Out-Null

& $python (Join-Path $projectRoot "tools\generate_gold_delta.py") $resolvedSource $resolvedGold $patchResource
if ($LASTEXITCODE -ne 0) {
    throw "Patch resource generation failed"
}

if (Test-Path -LiteralPath $overrideResource) {
    Remove-Item -LiteralPath $overrideResource -Force
}
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $resolvedOverride,
    $overrideResource,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

& $compiler /nologo /optimize+ /target:winexe /platform:anycpu `
    /out:$outputExe `
    /win32icon:$resolvedIcon `
    /reference:System.dll `
    /reference:System.Drawing.dll `
    /reference:System.IO.Compression.dll `
    /reference:System.IO.Compression.FileSystem.dll `
    /reference:System.Windows.Forms.dll `
    /resource:"$patchResource,KotorUniversalUI.goldpatch" `
    /resource:"$overrideResource,KotorUniversalUI.override3440x1440" `
    (Join-Path $projectRoot "app\patcher\KotorGoldPatcher.cs")
if ($LASTEXITCODE -ne 0) {
    throw "Patcher compilation failed"
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $outputExe
Write-Host "Built: $outputExe"
Write-Host "SHA-256: $($hash.Hash)"
