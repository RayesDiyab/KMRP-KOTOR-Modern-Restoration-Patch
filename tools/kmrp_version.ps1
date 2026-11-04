<#
.SYNOPSIS
    KMRP's version, or the path of the Windows installer named after it.

.DESCRIPTION
    The version is InstallCore.PatchVersion in src\patcher\InstallCore.cs, the one the
    installer reports and records. It is changed there by hand; every build and test
    reads it through this script, so the file names cannot drift from it.

    With -WindowsInstaller the result is the full path build_kmrp.ps1 writes:
    dist\KMRP-Windows-<version>.exe, the name the release assets have carried since
    1.5.0 (KMRP-Windows-1.5.0.exe, KMRP-Windows-1.5.1.exe), beside the AppImage's
    dist\KMRP-Linux-<version>-x86_64.AppImage.

.EXAMPLE
    & .\tools\kmrp_version.ps1                     # 1.6.0
    & .\tools\kmrp_version.ps1 -WindowsInstaller   # <project>\dist\KMRP-Windows-1.6.0.exe
#>
param([switch]$WindowsInstaller)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $projectRoot "src\patcher\InstallCore.cs"
$match = [regex]::Match((Get-Content -Raw -LiteralPath $source),
    'internal const string PatchVersion = "([^"]+)";')
if (-not $match.Success) { throw "PatchVersion was not found in $source" }
$version = $match.Groups[1].Value

if ($WindowsInstaller) { return (Join-Path $projectRoot ("dist\KMRP-Windows-{0}.exe" -f $version)) }
return $version
