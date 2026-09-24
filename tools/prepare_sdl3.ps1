# Pinned official x86 SDL SDK; generated dependencies stay under ignored build/.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$deps = Join-Path $root 'build/deps'
$archive = Join-Path $deps 'SDL3-devel-3.4.16-VC.zip'
$expected = '1A784CB2A5C64D56FE7A62090FE9D242D9865F235E4EA9678F1A6BA4E693E7DE'
New-Item -ItemType Directory -Force -Path $deps | Out-Null
if (-not (Test-Path -LiteralPath $archive)) {
    Invoke-WebRequest 'https://github.com/libsdl-org/SDL/releases/download/release-3.4.16/SDL3-devel-3.4.16-VC.zip' -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $expected) {
    throw 'SDL SDK hash mismatch; refusing this dependency.'
}
Expand-Archive -LiteralPath $archive -DestinationPath $deps -Force
$sdk = Join-Path $deps 'SDL3-3.4.16'
$bytes = [IO.File]::ReadAllBytes((Join-Path $sdk 'lib/x86/SDL3.dll'))
$pe = [BitConverter]::ToInt32($bytes, 0x3c)
if ([BitConverter]::ToUInt16($bytes, $pe + 4) -ne 0x14c) { throw 'SDL must be x86.' }
Copy-Item -LiteralPath (Join-Path $sdk 'lib/x86/SDL3.dll') -Destination (Join-Path $deps 'kmrp-sdl3.dll')
Write-Host 'Verified SDL 3.4.16 x86 SDK.'
