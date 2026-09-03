param(
    # Inputs that come from your own copy of the game. They default to
    # build-inputs\ inside the project, so the folder is self-contained and can be
    # moved anywhere. They are NOT committed -- .gitignore blocks the executable
    # and the texture pack, because they are BioWare's, not ours.
    #
    # A "..\" default was used until the project folder moved and the build broke
    # silently, which is why these now point inside the project. Override with a
    # parameter, with KMRP_SOURCE_EXE / KMRP_TEXTURE_PACK / KMRP_PYTHON, or in a
    # gitignored build.local.ps1 (copy build.local.example.ps1).
    [string]$SourceExe,
    [string]$TexturePack,
    [string]$Python,

    # In-repository inputs. These always move with the project.
    [string]$GoldExe = ".\build\kmrp\swkotor_gold_v19_areafog.exe",
    [string]$GoldOverride = ".\assets\override-3440x1440",
    [string]$UpstreamGuiRoot = ".\third_party\kotor-high-resolution-menus-1.5",
    [string]$IconPath = ".\assets\branding\favicon.ico",
    [string]$HdFonts = ".\assets\hd-fonts",
    [switch]$ReuseResources,

    # Progress is drawn with a redrawing bar. Pass -Plain for one line per event
    # instead, which is what you want when piping the build to a file or a log.
    [switch]$Plain
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $projectRoot "build\kmrp"
$resourceDir = Join-Path $buildDir "resources"
$distDir = Join-Path $projectRoot "dist"
$patchResource = Join-Path $buildDir "gold.kup"
$outputExe = Join-Path $distDir "KMRP - KOTOR Modern Restoration Patch.exe"

# Local, uncommitted machine settings, if any.
$localSettings = Join-Path $projectRoot "build.local.ps1"
if (Test-Path -LiteralPath $localSettings) { . $localSettings }

if (-not $SourceExe)   { $SourceExe   = $env:KMRP_SOURCE_EXE }
if (-not $SourceExe)   { $SourceExe   = $KmrpSourceExe }
if (-not $SourceExe)   { $SourceExe   = ".\build-inputs\swkotornopatch.exe" }
if (-not $TexturePack) { $TexturePack = $env:KMRP_TEXTURE_PACK }
if (-not $TexturePack) { $TexturePack = $KmrpTexturePack }
if (-not $TexturePack) { $TexturePack = ".\build-inputs\swpc_tex_gui.erf" }
if (-not $Python)      { $Python      = $env:KMRP_PYTHON }
if (-not $Python)      { $Python      = $KmrpPython }
if (-not $Python)      { $Python      = (Get-Command python -ErrorAction SilentlyContinue).Source }

# Absolute paths are used as given; relative ones are relative to the project.
# Join-Path would otherwise turn "C:\game\file.erf" into "<project>\C:\game\file.erf".
function Resolve-InputPath([string]$Path) {
    if ([System.IO.Path]::IsPathRooted($Path)) { return $Path }
    return (Join-Path $projectRoot $Path)
}

# ---------------------------------------------------------------- progress output
#
# The build takes minutes and does most of its work inside two child processes.
# Without this it looked hung, so each stage announces itself, draws a bar, and
# reports how long it took. The bar redraws in place with a carriage return;
# -Plain turns that off for logs and non-interactive shells.

$script:StepIndex = 0
$script:StepTotal = if ($ReuseResources) { 4 } else { 5 }
$script:StepStart = Get-Date
$script:BuildStart = Get-Date
$script:BarWidth = 32
$script:LineWidth = 96

function Write-Rule([string]$Text) {
    Write-Host ""
    Write-Host ("  " + $Text) -ForegroundColor DarkCyan
    Write-Host ("  " + ("-" * [Math]::Min($script:LineWidth, $Text.Length + 8))) -ForegroundColor DarkGray
}

function Write-Bar {
    param([int]$Percent, [string]$Label)
    if ($Percent -lt 0) { $Percent = 0 } elseif ($Percent -gt 100) { $Percent = 100 }
    $filled = [Math]::Round($script:BarWidth * $Percent / 100)
    $bar = ("=" * $filled).PadRight($script:BarWidth, ".")
    $line = "  [{0}] {1,3}%  {2}" -f $bar, $Percent, $Label
    if ($line.Length -gt $script:LineWidth) { $line = $line.Substring(0, $script:LineWidth) }
    if ($Plain) {
        Write-Host $line -ForegroundColor Cyan
    } else {
        Write-Host ("`r" + $line.PadRight($script:LineWidth)) -NoNewline -ForegroundColor Cyan
    }
}

function Write-Detail([string]$Text) {
    $line = "    " + $Text
    if ($line.Length -gt $script:LineWidth) { $line = $line.Substring(0, $script:LineWidth) }
    if (-not $Plain) { Write-Host ("`r" + "".PadRight($script:LineWidth)) -NoNewline }
    Write-Host ("`r" + $line) -ForegroundColor Gray
}

function Start-Step([string]$Name) {
    $script:StepIndex++
    $script:StepStart = Get-Date
    Write-Host ""
    Write-Host ("  [{0}/{1}] {2}" -f $script:StepIndex, $script:StepTotal, $Name) -ForegroundColor White
    Write-Progress -Activity "Building KMRP" -Status $Name `
        -PercentComplete ((($script:StepIndex - 1) / $script:StepTotal) * 100)
    Write-Bar -Percent 0 -Label $Name
}

function Complete-Step([string]$Detail = "") {
    $seconds = ((Get-Date) - $script:StepStart).TotalSeconds
    Write-Bar -Percent 100 -Label "done"
    if (-not $Plain) { Write-Host "" }
    $suffix = if ($Detail) { "  $Detail" } else { "" }
    Write-Host ("    finished in {0:n1}s{1}" -f $seconds, $suffix) -ForegroundColor DarkGreen
}

# Runs a child process, turning "[n/total] label" lines into bar updates and
# printing everything else as detail. Throws with the step name on a failure.
function Invoke-Tool {
    param([string]$Exe, [string[]]$Arguments, [string]$FailureMessage, [string]$Label)
    # 2>&1 turns a native program's stderr into ErrorRecord objects, and under
    # $ErrorActionPreference = "Stop" that is a TERMINATING NativeCommandError --
    # so a single harmless line on stderr aborts the build. pykotor emits
    # "WARNING(root): Invalid TXI command" while reading the game's own texture
    # metadata, which killed the run at step 3. Success is decided by the exit
    # code below, not by whether the tool said anything on stderr.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Exe @Arguments 2>&1 | ForEach-Object {
        $line = ([string]$_).TrimEnd()
        if ($line -match '^\s*\[(\d+)/(\d+)\]\s*(.*)$') {
            $done = [int]$Matches[1]
            $total = [int]$Matches[2]
            $percent = if ($total -gt 0) { [int](100 * $done / $total) } else { 0 }
            Write-Bar -Percent $percent -Label ("{0} {1}/{2}  {3}" -f $Label, $done, $total, $Matches[3])
        } elseif ($line) {
            Write-Detail $line
        }
    }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw $FailureMessage }
}

Write-Host ""
Write-Host "  KMRP - KOTOR Modern Restoration Patch" -ForegroundColor Cyan
Write-Host "  build" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 1. inputs
Start-Step "Checking build inputs"

$resolvedSource = Resolve-InputPath $SourceExe
$resolvedTexturePack = Resolve-InputPath $TexturePack

$missing = @()
if (-not (Test-Path -LiteralPath $resolvedSource)) {
    $missing += "  clean swkotor.exe  ->  $resolvedSource"
}
if (-not (Test-Path -LiteralPath $resolvedTexturePack)) {
    $missing += "  swpc_tex_gui.erf   ->  $resolvedTexturePack"
}
if ($missing.Count -gt 0) {
    throw ("Build inputs from your copy of the game are missing:`r`n" +
        ($missing -join "`r`n") +
        "`r`nCopy them there (see build-inputs\README.md), or pass -SourceExe / -TexturePack.")
}
if (-not $Python) {
    throw "Python was not found. Add it to PATH, pass -Python, or set KmrpPython in build.local.ps1."
}

$compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python was not found at $Python"
}
if (-not (Test-Path -LiteralPath $compiler)) {
    throw ".NET Framework C# compiler was not found at $compiler"
}

$resolvedSource = (Resolve-Path -LiteralPath $resolvedSource).Path
$resolvedTexturePack = (Resolve-Path -LiteralPath $resolvedTexturePack).Path
$resolvedGold = (Resolve-Path -LiteralPath (Resolve-InputPath $GoldExe)).Path
$resolvedGoldOverride = (Resolve-Path -LiteralPath (Resolve-InputPath $GoldOverride)).Path
$resolvedUpstream = (Resolve-Path -LiteralPath (Resolve-InputPath $UpstreamGuiRoot)).Path
$resolvedIcon = (Resolve-Path -LiteralPath (Resolve-InputPath $IconPath)).Path
$resolvedHdFonts = (Resolve-Path -LiteralPath (Resolve-InputPath $HdFonts)).Path
$geometry = (Resolve-Path -LiteralPath (Resolve-InputPath "assets\resolution-geometry.json")).Path

Write-Detail ("source exe   {0}  ({1:n0} bytes)" -f (Split-Path -Leaf $resolvedSource), (Get-Item $resolvedSource).Length)
Write-Detail ("gold exe     {0}" -f (Split-Path -Leaf $resolvedGold))
Write-Detail ("texture pack {0}  ({1:n0} MB)" -f (Split-Path -Leaf $resolvedTexturePack), ((Get-Item $resolvedTexturePack).Length / 1MB))
Write-Detail ("python       {0}" -f $Python)
New-Item -ItemType Directory -Force -Path $buildDir, $distDir | Out-Null
Complete-Step

# ---------------------------------------------------------------- 2. gold delta
Start-Step "Building the gold delta"
Invoke-Tool -Exe $Python -Label "chunk" -FailureMessage "Patch resource generation failed" -Arguments @(
    (Join-Path $projectRoot "tools\generate_gold_delta.py"),
    $resolvedSource, $resolvedGold, $patchResource)
Complete-Step ("{0:n0} KB" -f ((Get-Item $patchResource).Length / 1KB))

# ---------------------------------------------------------------- 3. resources
if (-not $ReuseResources) {
    Start-Step "Generating interface resources for every resolution"
    Invoke-Tool -Exe $Python -Label "resolution" -FailureMessage "Interface resource generation failed" -Arguments @(
        (Join-Path $projectRoot "tools\prepare_universal_resources.py"),
        $geometry, $resolvedUpstream, $resolvedGoldOverride, $resourceDir,
        $resolvedTexturePack, $resolvedHdFonts)
    $archives = @(Get-ChildItem -LiteralPath $resourceDir -Filter "gui-*.zip")
    Complete-Step ("{0} resolution archives" -f $archives.Count)
} else {
    Write-Host ""
    Write-Host "  [skipped] Interface resources reused from the previous build" -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------- 4. compile
Start-Step "Compiling the patcher"

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
    "/resource:$patchResource,Kmrp.goldpatch",
    "/resource:$(Join-Path $resourceDir 'override-common.zip'),Kmrp.override.common",
    "/resource:$(Join-Path $resourceDir 'resolutions.tsv'),Kmrp.resolutions",
    "/resource:$(Join-Path $projectRoot 'src\patcher\brand.png'),Kmrp.brand",
    "/resource:$(Join-Path $resourceDir 'GPL-3.0-KOTOR-High-Resolution-Menus.txt'),Kmrp.license.highresolutionmenus"
)

# Hand-supplied UI icons are optional: step icons fall back to vector glyphs,
# while the verified label simply falls back to text if its artwork is absent.
$iconNames = @("folder", "shield", "monitor", "tools", "verified", "missing")
$iconCount = 0
foreach ($iconName in $iconNames) {
    $iconPath = Join-Path $projectRoot "src\patcher\icons\$iconName.png"
    if (Test-Path -LiteralPath $iconPath) {
        $compilerArgs += "/resource:$iconPath,Kmrp.icon.$iconName"
        $iconCount++
    }
}
Write-Detail ("embedding {0} of {1} UI icons" -f $iconCount, $iconNames.Count)

$guiArchives = @(Get-ChildItem -LiteralPath $resourceDir -Filter "gui-*.zip" | Sort-Object Name)
$index = 0
foreach ($archive in $guiArchives) {
    $index++
    $resolution = $archive.BaseName.Substring(4)
    $compilerArgs += "/resource:$($archive.FullName),Kmrp.override.gui.$resolution"
    Write-Bar -Percent ([int](100 * $index / [Math]::Max(1, $guiArchives.Count))) `
        -Label ("embedding {0}/{1}  {2}" -f $index, $guiArchives.Count, $resolution)
}

$compilerArgs += (Join-Path $projectRoot "src\patcher\KmrpPatcher.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\AbilityIconGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\AssemblyInfo.cs")

Write-Bar -Percent 100 -Label "running the C# compiler"
Invoke-Tool -Exe $compiler -Arguments $compilerArgs -Label "compile" `
    -FailureMessage "KMRP compilation failed"
Complete-Step ("{0:n1} MB" -f ((Get-Item $outputExe).Length / 1MB))

# ---------------------------------------------------------------- 5. finalise
Start-Step "Finalising"

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
    Write-Detail "refreshed Explorer's icon cache for the rebuilt file"
}
catch {
    Write-Warning "The patcher was built, but Explorer's icon view could not be refreshed: $($_.Exception.Message)"
}

# Hashed with .NET rather than Get-FileHash: that cmdlet failed to resolve in a
# spawned Windows PowerShell host on this machine, and the hash is the one thing
# the build must always be able to report.
$sha = [System.Security.Cryptography.SHA256]::Create()
$stream = [System.IO.File]::OpenRead($outputExe)
try { $hashBytes = $sha.ComputeHash($stream) } finally { $stream.Dispose(); $sha.Dispose() }
$hashHex = [System.BitConverter]::ToString($hashBytes).Replace("-", "")
Complete-Step

Write-Progress -Activity "Building KMRP" -Completed
$total = (Get-Date) - $script:BuildStart

Write-Host ""
Write-Host ("  KMRP - KOTOR Modern Restoration Patch    built in {0:mm\:ss}" -f $total) -ForegroundColor Green
Write-Host ("  output    {0}" -f $outputExe) -ForegroundColor Gray
Write-Host ("  size      {0:n0} bytes" -f (Get-Item $outputExe).Length) -ForegroundColor Gray
Write-Host ("  SHA-256   {0}" -f $hashHex) -ForegroundColor Gray
Write-Host ""
