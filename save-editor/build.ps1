# Builds dist\KMRP Save Editor.exe beside this file: one file, no installer, no other files.
#
#   powershell -ExecutionPolicy Bypass -File save-editor\build.ps1
#
# Needs Rust (rustup, stable). Everything else is in this folder, so it builds on its own,
# outside KMRP; build.rs says where KMRP's fonts are looked for. Linux and macOS build
# with build.sh beside this file.
$ErrorActionPreference = "Stop"

$here = $PSScriptRoot
$dist = Join-Path $here "dist"
$exe = Join-Path $dist "KMRP Save Editor.exe"

Push-Location $here
try {
    cargo test --release
    if ($LASTEXITCODE -ne 0) { throw "the tests failed" }
    cargo build --release
    if ($LASTEXITCODE -ne 0) { throw "the editor did not build" }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $dist | Out-Null
Copy-Item -LiteralPath (Join-Path $here "build\target\release\kmrp-save-editor.exe") -Destination $exe -Force
$item = Get-Item -LiteralPath $exe
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
Write-Host ("{0}  {1:n0} bytes  SHA-256 {2}" -f $item.FullName, $item.Length, $hash)
