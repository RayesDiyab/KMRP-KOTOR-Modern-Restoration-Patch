param(
    [string]$SourceExe = "..\swkotornopatch.exe",
    [string]$GoldExe = ".\build\universal-patcher\swkotor_gold_v15_popup.exe",
    [string]$GoldOverride = ".\assets\override-3440x1440",
    [string]$UpstreamGuiRoot = ".\third_party\kotor-high-resolution-menus-1.5",
    [string]$IconPath = ".\favicon.ico",
    [string]$TexturePack = "..\TexturePacks\swpc_tex_gui.erf",
    [string]$HdFonts = ".\assets\hd-fonts",
    [switch]$ReuseResources
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $projectRoot "build\universal-patcher"
$resourceDir = Join-Path $buildDir "resources"
$distDir = Join-Path $projectRoot "dist"
$patchResource = Join-Path $buildDir "gold.kup"
$outputExe = Join-Path $distDir "KMRP - KOTOR Modern Restoration Patch.exe"
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
$resolvedGoldOverride = (Resolve-Path -LiteralPath (Join-Path $projectRoot $GoldOverride)).Path
$resolvedUpstream = (Resolve-Path -LiteralPath (Join-Path $projectRoot $UpstreamGuiRoot)).Path
$resolvedIcon = (Resolve-Path -LiteralPath (Join-Path $projectRoot $IconPath)).Path
$resolvedTexturePack = (Resolve-Path -LiteralPath (Join-Path $projectRoot $TexturePack)).Path
$resolvedHdFonts = (Resolve-Path -LiteralPath (Join-Path $projectRoot $HdFonts)).Path
$geometry = (Resolve-Path -LiteralPath (Join-Path $projectRoot "assets\resolution-geometry.json")).Path

New-Item -ItemType Directory -Force -Path $buildDir, $distDir | Out-Null

& $python (Join-Path $projectRoot "tools\generate_gold_delta.py") $resolvedSource $resolvedGold $patchResource
if ($LASTEXITCODE -ne 0) {
    throw "Patch resource generation failed"
}

if (-not $ReuseResources) {
    & $python (Join-Path $projectRoot "tools\prepare_universal_resources.py") `
        $geometry $resolvedUpstream $resolvedGoldOverride $resourceDir $resolvedTexturePack $resolvedHdFonts
    if ($LASTEXITCODE -ne 0) {
        throw "Universal interface resource generation failed"
    }
}

$compilerArgs = @(
    "/nologo",
    "/optimize+",
    "/target:winexe",
    "/platform:anycpu",
    "/out:$outputExe",
    "/win32icon:$resolvedIcon",
    "/reference:System.dll",
    "/reference:System.Drawing.dll",
    "/reference:System.IO.Compression.dll",
    "/reference:System.IO.Compression.FileSystem.dll",
    "/reference:System.Windows.Forms.dll",
    "/resource:$patchResource,KotorUniversalUI.goldpatch",
    "/resource:$(Join-Path $resourceDir 'override-common.zip'),KotorUniversalUI.override.common",
    "/resource:$(Join-Path $resourceDir 'resolutions.tsv'),KotorUniversalUI.resolutions",
    "/resource:$(Join-Path $projectRoot 'app\patcher\brand.png'),KotorUniversalUI.brand",
    "/resource:$(Join-Path $resourceDir 'GPL-3.0-KOTOR-High-Resolution-Menus.txt'),KotorUniversalUI.license.highresolutionmenus"
)

# Hand-supplied UI icons are optional: step icons fall back to vector glyphs,
# while the verified label simply falls back to text if its artwork is absent.
foreach ($iconName in @("folder", "shield", "monitor", "tools", "verified", "missing")) {
    $iconPath = Join-Path $projectRoot "app\patcher\icons\$iconName.png"
    if (Test-Path -LiteralPath $iconPath) {
        $compilerArgs += "/resource:$iconPath,KotorUniversalUI.icon.$iconName"
        Write-Host "  icon: $iconName"
    }
}

Get-ChildItem -LiteralPath $resourceDir -Filter "gui-*.zip" | Sort-Object Name | ForEach-Object {
    $resolution = $_.BaseName.Substring(4)
    $compilerArgs += "/resource:$($_.FullName),KotorUniversalUI.override.gui.$resolution"
}
$compilerArgs += (Join-Path $projectRoot "app\patcher\KotorUniversalPatcher.cs")
$compilerArgs += (Join-Path $projectRoot "app\patcher\AbilityIconGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "app\patcher\AssemblyInfo.cs")

& $compiler $compilerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Universal patcher compilation failed"
}

# Explorer aggressively caches executable icons by path. KMRP is rebuilt in place,
# so notify the shell that this exact file changed instead of leaving the previous
# build's artwork visible until Windows eventually expires its cache entry.
try {
    if (-not ("KmrpShellRefresh" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class KmrpShellRefresh
{
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    public static extern void SHChangeNotify(uint eventId, uint flags,
        string item1, IntPtr item2);
}
"@
    }
    # SHCNE_UPDATEITEM | SHCNF_PATHW | SHCNF_FLUSH
    [KmrpShellRefresh]::SHChangeNotify(0x00002000, 0x00001005,
        $outputExe, [IntPtr]::Zero)
}
catch {
    Write-Warning "The patcher was built, but Explorer's icon view could not be refreshed: $($_.Exception.Message)"
}

$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $outputExe
Write-Host "Built: $outputExe"
Write-Host "SHA-256: $($hash.Hash)"
