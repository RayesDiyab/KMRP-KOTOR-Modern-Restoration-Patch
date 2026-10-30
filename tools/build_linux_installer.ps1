<#
.SYNOPSIS
    Builds KMRP's native Linux installer (issue 76, docs/linux-appimage-installer.md).

.DESCRIPTION
    Embeds the Windows installer's own resources, under the same names, from the list
    build_kmrp.ps1 writes as it compiles (build\kmrp\installer-resources.tsv), so both
    installers carry the same KPM runtime, patches, art pack and tables. Run build_kmrp.ps1
    first. Then publishes src\installer-linux for linux-x64 as one self-contained file with
    the .NET 8 SDK on Windows: build\installer-linux\publish\kmrp-installer. Then packs it
    as dist\KMRP-Linux-<version>-x86_64.AppImage in WSL (tools\build_linux_appimage.sh),
    unless -NoAppImage is given.

.EXAMPLE
    pwsh -File tools\build_linux_installer.ps1
#>
[CmdletBinding()]
param(
    # Publish the program only, without packing the AppImage (which needs WSL).
    [switch]$NoAppImage
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$list = Join-Path $projectRoot "build\kmrp\installer-resources.tsv"
if (-not (Test-Path -LiteralPath $list)) { throw "$list is missing: run build_kmrp.ps1 first." }
$out = Join-Path $projectRoot "build\installer-linux"
New-Item -ItemType Directory -Force -Path $out | Out-Null

$items = foreach ($line in [System.IO.File]::ReadAllLines($list)) {
    if (-not $line) { continue }
    $name, $path = $line -split "`t", 2
    if (-not (Test-Path -LiteralPath $path)) { throw "resource $name names $path, which is missing" }
    '    <EmbeddedResource Include="{0}" LogicalName="{1}" />' -f [System.Security.SecurityElement]::Escape($path), $name
}
$props = Join-Path $out "Resources.props"
$text = "<Project>`n  <ItemGroup>`n" + ($items -join "`n") + "`n  </ItemGroup>`n</Project>`n"
[System.IO.File]::WriteAllText($props, $text, (New-Object System.Text.UTF8Encoding $false))
Write-Host ("{0} resources from {1}" -f @($items).Count, $list)

$dotnet = "C:\Program Files\dotnet\dotnet.exe"
& $dotnet publish (Join-Path $projectRoot "src\installer-linux\KmrpLinux.csproj") -c Release -r linux-x64 `
    --self-contained true -p:PublishSingleFile=true "-p:KmrpResources=$props" -o (Join-Path $out "publish")
if ($LASTEXITCODE -ne 0) { throw "dotnet publish failed" }
$file = Get-Item (Join-Path $out "publish\kmrp-installer")
Write-Host ("{0}: {1:n0} bytes, SHA-256 {2}" -f $file.FullName, $file.Length, (Get-FileHash $file.FullName).Hash)
if ($NoAppImage) { return }

# The AppImage, packed on Linux (WSL here) by tools/build_linux_appimage.sh: its icon is the
# Windows installer's (assets\branding\favicon.ico) as a 256-pixel PNG, its name carries the
# version the installer reports (GoldPatch.PatchVersion).
$icon = Join-Path $out "kmrp-installer.png"
& python -c "import sys; from PIL import Image; im = Image.open(sys.argv[1]); im.size = (256, 256); im.save(sys.argv[2])" `
    (Join-Path $projectRoot "assets\branding\favicon.ico") $icon
if ($LASTEXITCODE -ne 0) { throw "the icon could not be made" }
$version = [regex]::Match((Get-Content -Raw -LiteralPath (Join-Path $projectRoot "src\patcher\InstallCore.cs")),
    'internal const string PatchVersion = "([^"]+)";').Groups[1].Value
$script = (& wsl.exe wslpath -a ((Join-Path $projectRoot "tools\build_linux_appimage.sh") -replace '\\', '/')).Trim()
& wsl.exe bash $script $version
if ($LASTEXITCODE -ne 0) { throw "the AppImage could not be packed" }
