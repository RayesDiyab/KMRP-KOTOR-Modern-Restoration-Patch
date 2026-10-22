# Builds dist\KMRP Font Converter.exe beside this file: one file, .NET Framework 4 (in every
# Windows since 8, and in Wine's wine-mono under Proton), no other files.
#
#   powershell -ExecutionPolicy Bypass -File font-converter\build.ps1 [-Refresh] [-Python python]
#
# Everything it needs is in this folder, so it builds on its own, outside KMRP. The
# examples and font metrics it carries are in data\, made from KMRP's (New) Original HD
# Font by make_data.py (needs Pillow); -Refresh makes them again, from the KMRP checkout
# this folder sits in (assets\hd-original-fonts), before compiling them in as resources.
param([switch]$Refresh, [string]$Python = "python")
$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$data = Join-Path $here "data"
$dist = Join-Path $here "dist"
$exe = Join-Path $dist "KMRP Font Converter.exe"
$compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $compiler)) { throw ".NET Framework C# compiler was not found at $compiler" }

if ($Refresh) {
    & $Python (Join-Path $here "make_data.py") $data
    if ($LASTEXITCODE -ne 0) { throw "make_data.py failed" }
}
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$resources = @(
    "/resource:$data\references.txt,references.txt",
    "/resource:$data\examples.txt,examples.txt",
    "/resource:$here\kmrp-logo.png,kmrp-logo.png",
    # The installer's settings gear (src/patcher/icons/Settings.png, cropped to its ink and
    # made 512 px), line art drawn tinted.
    "/resource:$here\settings.png,settings.png"
)
# KMRP's own fonts for the window's text (SIL OFL 1.1, fonts\OFL.txt), TrueType: GDI+
# cannot load the CFF outlines of the OTF files.
foreach ($ttf in Get-ChildItem -LiteralPath (Join-Path $here "fonts") -Filter *.ttf) {
    $resources += "/resource:$($ttf.FullName),fonts.$($ttf.Name)"
}
foreach ($logo in "logo-deadlystream.png", "logo-github.png") {
    $path = Join-Path $here $logo
    if (Test-Path -LiteralPath $path) { $resources += "/resource:$path,$logo" }
}
foreach ($png in Get-ChildItem -LiteralPath (Join-Path $data "examples") -Filter *.png) {
    $resources += "/resource:$($png.FullName),examples.$($png.Name)"
}

$sources = Get-ChildItem -LiteralPath $here -Filter *.cs | ForEach-Object { $_.FullName }
& $compiler /nologo /optimize+ /target:winexe /platform:anycpu "/out:$exe" `
    "/win32icon:$here\favicon.ico" `
    /reference:System.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /reference:System.Core.dll `
    $resources $sources
if ($LASTEXITCODE -ne 0) { throw "The converter did not compile" }

$item = Get-Item -LiteralPath $exe
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Host ("{0}  {1:n0} bytes  SHA-256 {2}" -f $item.FullName, $item.Length, $hash)
