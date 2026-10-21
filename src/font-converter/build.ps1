# Builds dist\KMRP Font Converter.exe: one file, .NET Framework 4 (in every Windows since 8,
# and in Wine's wine-mono under Proton), no other files.
#
#   powershell -ExecutionPolicy Bypass -File src\font-converter\build.ps1 [-Python python]
#
# The examples and font metrics it carries are made from assets\hd-original-fonts by
# tools\build_font_converter_data.py (needs Pillow), then compiled in as resources.
param([string]$Python = "python")
$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$root = (Resolve-Path (Join-Path $here "..\..")).Path
$data = Join-Path $root "build\font-converter"
$dist = Join-Path $root "dist"
$exe = Join-Path $dist "KMRP Font Converter.exe"
$compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $compiler)) { throw ".NET Framework C# compiler was not found at $compiler" }

& $Python (Join-Path $root "tools\build_font_converter_data.py") $data
if ($LASTEXITCODE -ne 0) { throw "build_font_converter_data.py failed" }
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$resources = @(
    "/resource:$data\references.txt,references.txt",
    "/resource:$data\examples.txt,examples.txt",
    "/resource:$here\kmrp-logo.png,kmrp-logo.png"
)
foreach ($logo in "logo-deadlystream.png", "logo-github.png") {
    $path = Join-Path $here $logo
    if (Test-Path -LiteralPath $path) { $resources += "/resource:$path,$logo" }
}
foreach ($png in Get-ChildItem -LiteralPath (Join-Path $data "examples") -Filter *.png) {
    $resources += "/resource:$($png.FullName),examples.$($png.Name)"
}

$sources = Get-ChildItem -LiteralPath $here -Filter *.cs | ForEach-Object { $_.FullName }
& $compiler /nologo /optimize+ /target:winexe /platform:anycpu "/out:$exe" `
    "/win32icon:$root\src\patcher\favicon.ico" `
    /reference:System.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /reference:System.Core.dll `
    $resources $sources
if ($LASTEXITCODE -ne 0) { throw "The converter did not compile" }

$item = Get-Item -LiteralPath $exe
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Host ("{0}  {1:n0} bytes  SHA-256 {2}" -f $item.FullName, $item.Length, $hash)
