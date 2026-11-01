param(
    # The texture pack comes from your own copy of the game and defaults to
    # build-inputs\ inside the project. It is ignored, as are all game binaries.
    # Engine fixes are built from tracked source; no game EXE is required.
    #
    # Override with -TexturePack, KMRP_TEXTURE_PACK or build.local.ps1.
    [string]$TexturePack,
    [string]$Python,

    # In-repository inputs. These always move with the project.
    [string]$GoldOverride = ".\assets\override-3440x1440",
    [string]$UpstreamGuiRoot = ".\third_party\Included\kotor-high-resolution-menus-1.5",
    # Third-party Override mods bundled with their authors' permission.
    [string[]]$BundledOverride = @(
        ".\third_party\Included\Party Portraits by MadDerp",
        ".\third_party\Included\KOTOR1 HD ICON PACK ver1.0 1.0.0 by JackInTheBox\Override"
    ),
    # Lets a variant build sit beside the standard one instead of overwriting it.
    [string]$OutputName = "KMRP - KOTOR Modern Restoration Patch",
    [string]$IconPath = ".\assets\branding\favicon.ico",
    [string]$HdFonts = ".\assets\hd-fonts",
    [switch]$ReuseResources,
    # Regenerates step 3 even when its inputs are unchanged (the fingerprint below
    # normally decides; this is for a doubt, not for everyday builds).
    [switch]$FreshResources,
    # The same for step 6, the runtime, both modules and their patches.
    [switch]$FreshModules,

    # Progress is drawn with a redrawing bar. Pass -Plain for one line per event
    # instead, which is what you want when piping the build to a file or a log.
    [switch]$Plain
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "tools/prepare_sdl3.ps1")
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $projectRoot "build\kmrp"
$resourceDir = Join-Path $buildDir "resources"
$distDir = Join-Path $projectRoot "dist"
$engineSource = Join-Path $buildDir "windows-engine.bin"
$outputExe = Join-Path $distDir ($OutputName + ".exe")

# Local, uncommitted machine settings, if any.
$localSettings = Join-Path $projectRoot "build.local.ps1"
if (Test-Path -LiteralPath $localSettings) { . $localSettings }

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
# The engine assembly step includes relocation generation and proof.
$script:StepTotal = if ($ReuseResources) { 7 } else { 8 }
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

# ---------------------------------------------------------------- input fingerprints
# A step whose inputs have not changed since it last ran reuses what it made then
# (2026-10-27, the maintainer: step 3 regenerated all 66 resolutions, about 15 minutes,
# on every build). The fingerprint is the SHA-256 of every input file's path, size and
# last-write time, sorted, plus any extra text (tool versions); a git checkout, an edit
# or a new file changes it. A file named on its own (not a folder) counts by its content
# instead, as some (the blend table) are written again on every build with the same bytes.
# A Python file counts by its code, docstrings and comments left out
# (tools\source_fingerprint.py, 2026-10-27), so rewording a comment in tools\ makes nothing
# again. Kept beside the step's output; written only after the step succeeds, so a failed
# or stopped run is never taken as done.
# -Reach names the step's entry tools: of tools\, only what those reach counts (audit S-10).
function Get-InputFingerprint([string[]]$Paths, [string[]]$Extra = @(), [string]$Reach = "") {
    $lines = New-Object System.Collections.Generic.List[string]
    $codeFolders = New-Object System.Collections.Generic.List[string]
    foreach ($path in $Paths) {
        if (-not $path) { continue }
        if (Test-Path -LiteralPath $path -PathType Leaf) {
            $item = Get-Item -LiteralPath $path
            $lines.Add(("{0}|{1}" -f $item.FullName.ToLowerInvariant(), (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash))
        } elseif (Test-Path -LiteralPath $path -PathType Container) {
            $codeFolders.Add($path)
            foreach ($item in Get-ChildItem -LiteralPath $path -Recurse -File -Force) {
                if ($item.FullName -match '\\__pycache__\\') { continue }
                # Python files by their code instead (below): a comment or docstring edited
                # in tools\ made every slow step again (2026-10-27).
                if ($item.Extension -eq ".py") { continue }
                $lines.Add(("{0}|{1}|{2}" -f $item.FullName.ToLowerInvariant(), $item.Length, $item.LastWriteTimeUtc.Ticks))
            }
        } else {
            $lines.Add(("{0}|missing" -f $path.ToLowerInvariant()))
        }
    }
    if ($codeFolders.Count -gt 0) {
        $reachArguments = if ($Reach) { @("--reach", $Reach) } else { @() }
        $code = & $Python (Join-Path $projectRoot "tools\source_fingerprint.py") @reachArguments @codeFolders
        if ($LASTEXITCODE -ne 0) { throw "tools\source_fingerprint.py failed" }
        foreach ($line in $code) { $lines.Add($line) }
    }
    $sorted = @($lines | Sort-Object) + @($Extra)
    $bytes = [Text.Encoding]::UTF8.GetBytes(($sorted -join "`n"))
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '') }
    finally { $sha.Dispose() }
}

function Test-StepCurrent([string]$StampPath, [string]$Fingerprint) {
    return (Test-Path -LiteralPath $StampPath -PathType Leaf) -and
        ((Get-Content -LiteralPath $StampPath -Raw).Trim() -eq $Fingerprint)
}

Write-Host ""
Write-Host "  KMRP - KOTOR Modern Restoration Patch" -ForegroundColor Cyan
Write-Host "  build" -ForegroundColor DarkGray

# ---------------------------------------------------------------- 1. inputs
Start-Step "Checking build inputs"

$resolvedTexturePack = Resolve-InputPath $TexturePack

$missing = @()
if (-not (Test-Path -LiteralPath $resolvedTexturePack)) {
    $missing += "  swpc_tex_gui.erf   ->  $resolvedTexturePack"
}
if ($missing.Count -gt 0) {
    throw ("Build inputs from your copy of the game are missing:`r`n" +
        ($missing -join "`r`n") +
        "`r`nCopy them there (see build-inputs\README.md), or pass -TexturePack.")
}
if (-not $Python) {
    throw "Python was not found. Add it to PATH, pass -Python, or set KmrpPython in build.local.ps1."
}

$compiler = "C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python was not found at $Python"
}
# The controller module's cmd script runs its Python tools under vcvars, whose PATH can
# name another interpreter first (one without shapely, 2026-10-27); it uses this one.
$env:KMRP_PYTHON = $Python
if (-not (Test-Path -LiteralPath $compiler)) {
    throw ".NET Framework C# compiler was not found at $compiler"
}

$resolvedTexturePack = (Resolve-Path -LiteralPath $resolvedTexturePack).Path
$resolvedGoldOverride = (Resolve-Path -LiteralPath (Resolve-InputPath $GoldOverride)).Path
$resolvedUpstream = (Resolve-Path -LiteralPath (Resolve-InputPath $UpstreamGuiRoot)).Path
$resolvedIcon = (Resolve-Path -LiteralPath (Resolve-InputPath $IconPath)).Path
$resolvedHdFonts = (Resolve-Path -LiteralPath (Resolve-InputPath $HdFonts)).Path
$geometry = (Resolve-Path -LiteralPath (Resolve-InputPath "assets\resolution-geometry.json")).Path
$resolvedBundled = @($BundledOverride | ForEach-Object { (Resolve-Path -LiteralPath (Resolve-InputPath $_)).Path })

Write-Detail ("texture pack {0}  ({1:n0} MB)" -f (Split-Path -Leaf $resolvedTexturePack), ((Get-Item $resolvedTexturePack).Length / 1MB))
Write-Detail ("python       {0}" -f $Python)
New-Item -ItemType Directory -Force -Path $buildDir, $distDir | Out-Null

# The build's date: when the commit being built was made, in CEST (UTC+02:00, all year).
# Taken from git, not from this PC's clock, so everyone who builds a commit gets the
# same date, and every later commit a later one. The installer writes it into the
# game's manifest and compares it with an installed KMRP's to tell an older build from
# a newer one, whether or not the version was raised (KpmEdition.cs, BuildStamp; the
# maintainer, 2026-10-19). Uncommitted changes do not change it: such a build has its
# commit's date.
$commitSeconds = (& git -C $projectRoot log -1 --format=%ct HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or -not ($commitSeconds -match '^\d+$')) {
    throw "The build's date is the commit's, from git, and git could not give it. Build from a git checkout with git on PATH."
}
$commitId = (& git -C $projectRoot rev-parse --short HEAD 2>$null)
$buildStamp = [DateTimeOffset]::FromUnixTimeSeconds([long]$commitSeconds).ToOffset([TimeSpan]::FromHours(2)).ToString(
    "yyyy-MM-dd'T'HH:mm:sszzz", [Globalization.CultureInfo]::InvariantCulture)
$buildStampFile = Join-Path $buildDir "build-stamp.txt"
[IO.File]::WriteAllText($buildStampFile, $buildStamp, [Text.Encoding]::ASCII)
$uncommitted = @(& git -C $projectRoot status --porcelain --untracked-files=no 2>$null).Count -gt 0
Write-Detail ("build date   {0} CEST, commit {1}{2}" -f $buildStamp.Substring(0, 16).Replace('T', ' '), $commitId,
    $(if ($uncommitted) { ", with uncommitted changes" } else { "" }))
Complete-Step

# ---------------------------------------------------------------- 2. source-built engine patches
Start-Step "Assembling Windows engine fixes from source"
Invoke-Tool -Exe $Python -Label "engine" -FailureMessage "Source engine patch generation failed" -Arguments @(
    (Join-Path $projectRoot "tools\build_windows_engine.py"), "--out", $engineSource)
Complete-Step ("{0:n0} KB" -f ((Get-Item $engineSource).Length / 1KB))

# ---------------------------------------------------------------- 3. resources
# Everything step 3 reads: its inputs, every tool it imports (all of tools\, as it
# imports a dozen), the art under assets\ and the bundled mods, the per-scale font
# sets, and the Python and PyKotor it runs on.
$fontScaleSets = Join-Path $projectRoot "build\fonts"
$resourceStamp = Join-Path $resourceDir "inputs.sha256"
$pythonVersion = (& $Python -c "import sys, importlib.metadata as m; print(sys.version, m.version('pykotor'))" 2>$null) -join " "
$resourceInputs = @(
    (Join-Path $projectRoot "tools"), (Join-Path $projectRoot "assets"),
    (Join-Path $projectRoot "third_party\Included"), $resolvedUpstream, $resolvedGoldOverride,
    $resolvedTexturePack, $resolvedHdFonts, $geometry, $fontScaleSets) + $resolvedBundled
$resourceFingerprint = Get-InputFingerprint -Paths $resourceInputs -Reach "prepare_universal_resources" `
    -Extra @("python $pythonVersion", "bundled $($resolvedBundled -join ';')")
$resourcesCurrent = (-not $FreshResources) -and (Test-StepCurrent $resourceStamp $resourceFingerprint) -and
    (Test-Path -LiteralPath (Join-Path $resourceDir "override-common.zip"))
if ($resourcesCurrent) {
    Write-Host ""
    Write-Host "  [cached] Interface resources: inputs unchanged since they were made" -ForegroundColor DarkGreen
}
if (-not $ReuseResources -and -not $resourcesCurrent) {
    Start-Step "Generating interface resources for every resolution"
    # Built as a variable rather than inline: `-Arguments @(...) + $list` binds only
    # the array literal and silently drops the rest, which shipped a build with none
    # of the bundled Override mods in it.
    $resourceArgs = @(
        (Join-Path $projectRoot "tools\prepare_universal_resources.py"),
        $geometry, $resolvedUpstream, $resolvedGoldOverride, $resourceDir,
        $resolvedTexturePack, $resolvedHdFonts)
    # Font atlases baked at each resolution's own scale, so the engine draws one
    # texel per pixel instead of point-sampling a single 3.0 bake up or down.
    # Produced by tools/build_font_scale_sets.py, cached under build/fonts, and
    # gitignored because it is 1.4 GB raw for 15 MB of shipped payload. Without
    # it the build still works and falls back to the shared atlas -- which is the
    # behaviour issue #16 reports as pixelated text, so say so rather than
    # quietly producing it.
    if (Test-Path -LiteralPath $fontScaleSets) {
        $resourceArgs += "--font-scale-sets"
        $resourceArgs += $fontScaleSets
    } else {
        Write-Host ""
        Write-Host "  [warning] build\fonts is missing, so every resolution will reuse" -ForegroundColor DarkYellow
        Write-Host "            the 3.0 atlas and text will be resampled. Run:" -ForegroundColor DarkYellow
        Write-Host "            python tools\build_font_scale_sets.py <erf> build\fonts" -ForegroundColor DarkYellow
    }
    if ($resolvedBundled.Count -gt 0) {
        $resourceArgs += "--bundled-override"
        $resourceArgs += $resolvedBundled
    }
    Invoke-Tool -Exe $Python -Label "resolution" -FailureMessage "Interface resource generation failed" -Arguments $resourceArgs
    $archives = @(Get-ChildItem -LiteralPath $resourceDir -Filter "gui-*.zip")
    Set-Content -LiteralPath $resourceStamp -Value $resourceFingerprint -Encoding ascii
    Complete-Step ("{0} resolution archives" -f $archives.Count)
} elseif ($ReuseResources) {
    Write-Host ""
    Write-Host "  [skipped] Interface resources reused from the previous build" -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------- 4. layout pool
# The installer embeds one pool in place of the 66 resolution archives. They
# share most of their files -- a prompt badge is drawn for its button's size, and
# many buttons are the same size at many resolutions -- so the archives were
# 118 MB and their distinct files 58 MB. The archives stay in the resource folder,
# because the regression checks read them, and the packer stops the build unless
# every resolution rebuilt from the pool matches its archive. Runs with
# -ReuseResources as well, so the pool always matches the archives beside it.
# Cached like step 3: the pool is remade only when the archives or the tools change.
$layoutPool = Join-Path $buildDir "resolution-layouts.zip"
$poolStamp = $layoutPool + ".inputs.sha256"
$poolFingerprint = Get-InputFingerprint -Paths @($resourceDir, (Join-Path $projectRoot "tools")) `
    -Reach "pack_resolution_layouts" -Extra @("python $pythonVersion")
if ((Test-Path -LiteralPath $layoutPool) -and (Test-StepCurrent $poolStamp $poolFingerprint)) {
    Write-Host ""
    Write-Host "  [cached] Resolution layout pool: archives unchanged since it was made" -ForegroundColor DarkGreen
} else {
    Start-Step "Pooling the resolution layouts"
    Invoke-Tool -Exe $Python -Label "pool" -FailureMessage "Pooling the resolution layouts failed" -Arguments @(
        (Join-Path $projectRoot "tools\pack_resolution_layouts.py"), $resourceDir, $layoutPool)
    Set-Content -LiteralPath $poolStamp -Value $poolFingerprint -Encoding ascii
    Complete-Step ("{0:n1} MB" -f ((Get-Item $layoutPool).Length / 1MB))
}

# ---------------------------------------------------------------- 4a. the blend table
# For a resolution the build has no set for, the installer blends the .gui files
# from the finished sets around it (src/patcher/GuiBlend.cs), from the table the
# Mac installer blends from too (tools/build_gui_blend_table.py): per file a
# template, the fields that vary and their value in each set. Gzipped, it embeds
# as Kmrp.guiblend. Runs with -ReuseResources as well, so it always matches the
# archives beside it.
Start-Step "Packing the blend table for other resolutions"
$blendTable = Join-Path $buildDir "gui-blend.bin"
Invoke-Tool -Exe $Python -Label "blend" -FailureMessage "Packing the blend table failed" -Arguments @(
    (Join-Path $projectRoot "tools\build_gui_blend_table.py"), $resourceDir, $blendTable)
$blendResource = Join-Path $buildDir "gui-blend.bin.gz"
$blendInput = [System.IO.File]::OpenRead($blendTable)
$blendOutput = [System.IO.File]::Create($blendResource)
$blendZip = New-Object System.IO.Compression.GZipStream($blendOutput, [System.IO.Compression.CompressionLevel]::Optimal)
try { $blendInput.CopyTo($blendZip) } finally { $blendZip.Dispose(); $blendOutput.Dispose(); $blendInput.Dispose() }
Complete-Step ("{0:n1} MB, {1:n1} MB gzipped" -f ((Get-Item $blendTable).Length / 1MB), ((Get-Item $blendResource).Length / 1MB))

# ---------------------------------------------------------------- 5. compiler arguments
# What the installer embeds; step 7 compiles it from these.
$compilerArgs = @(
    "/nologo",
    "/optimize+",
    "/target:winexe",
    # 32-bit since 2026-10-19: it loads KMRP's module, which is x86, to make the art of
    # every size before the game first starts (ArtPreparation, KpmEdition.cs).
    "/platform:x86",
    "/out:$outputExe",
    "/win32icon:$resolvedIcon",
    "/reference:System.dll",
    "/reference:System.Drawing.dll",
    "/reference:System.IO.Compression.dll",
    "/reference:System.IO.Compression.FileSystem.dll",
    "/reference:System.Windows.Forms.dll",
    "/resource:$engineSource,Kmrp.engine.source",
    "/resource:$(Join-Path $resourceDir 'resolutions.tsv'),Kmrp.resolutions",
    "/resource:$(Join-Path $projectRoot 'src\patcher\brand.png'),Kmrp.brand",
    "/resource:$(Join-Path $resourceDir 'GPL-3.0-KOTOR-High-Resolution-Menus.txt'),Kmrp.license.highresolutionmenus"
    # KMRP's module, its SDL and its patch are embedded in step 7 as one file, the
    # .kpatch (Kmrp.kpatch): the installer takes the module out of it.
)

# Hand-supplied UI icons are optional: step icons fall back to vector glyphs,
# while the verified label simply falls back to text if its artwork is absent.
$iconNames = @("folder", "shield", "monitor", "tools", "verified", "missing", "Settings")
$iconCount = 0
foreach ($iconName in $iconNames) {
    $iconPath = Join-Path $projectRoot "src\patcher\icons\$iconName.png"
    if (Test-Path -LiteralPath $iconPath) {
        $compilerArgs += "/resource:$iconPath,Kmrp.icon.$iconName"
        $iconCount++
    }
}
Write-Detail ("embedding {0} of {1} UI icons" -f $iconCount, $iconNames.Count)

# Every resolution's layout, from the pool built in step 4. The installer reads
# it through GuiPool (src/patcher/KmrpPatcher.cs). Until 2026-09-25 each of the
# 49 archives was embedded whole, as Kmrp.override.gui.<W>x<H>.
# Not embedded since 2026-10-04: the installer no longer writes Override files. The
# patch's module carries every resolution's files (tools/build_native_assets.py reads
# the same archives), so $layoutPool is still built, for the --derive-gui tooling and
# the macOS build, but stays out of the installer.
$compilerArgs += "/resource:$blendResource,Kmrp.guiblend"
$compilerArgs += "/resource:$buildStampFile,Kmrp.build.stamp"

$compilerArgs += (Join-Path $projectRoot "src\patcher\KmrpPatcher.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\AbilityIconGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\GameArtGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\ControllerPromptGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\AssemblyInfo.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\KpmEdition.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\WindowsEnginePatch.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\GuiBlend.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\InstallCore.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\InstallPlatform.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\InstallPlatform.Windows.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\ArtPreparation.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\LightField.cs")

# Properties -> Details must name the version the install record names. The two live
# in different files and nothing compares them at run time, so they drifted twice:
# the v2.10.0 release reported 2.7.0, and 2.11.0-movieaspect was built reporting
# 2.10.0-mapnotes. Refuse to compile while they disagree.
$patchVersion = [regex]::Match(
    (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "src\patcher\InstallCore.cs")),
    'internal const string PatchVersion = "([^"]+)";').Groups[1].Value
$assemblyInfo = Get-Content -Raw -LiteralPath (Join-Path $projectRoot "src\patcher\AssemblyInfo.cs")
$versionFields = @{}
foreach ($field in @("AssemblyVersion", "AssemblyFileVersion", "AssemblyInformationalVersion")) {
    $versionFields[$field] = [regex]::Match($assemblyInfo, $field + '\("([^"]+)"\)').Groups[1].Value
}
$numericVersion = ($patchVersion -split "-")[0] + ".0"
if (-not $patchVersion -or
        $versionFields["AssemblyInformationalVersion"] -ne $patchVersion -or
        $versionFields["AssemblyFileVersion"] -ne $numericVersion -or
        $versionFields["AssemblyVersion"] -ne $numericVersion) {
    throw ("Version mismatch: PatchVersion '{0}' in InstallCore.cs, but AssemblyInfo.cs has " +
        "AssemblyVersion '{1}', AssemblyFileVersion '{2}', AssemblyInformationalVersion '{3}' " +
        "(expected '{4}', '{4}', '{0}').") -f $patchVersion, $versionFields["AssemblyVersion"],
        $versionFields["AssemblyFileVersion"], $versionFields["AssemblyInformationalVersion"], $numericVersion
}
Write-Host ("    version {0}, matching Properties -> Details" -f $patchVersion) -ForegroundColor DarkGray

# ---------------------------------------------------------------- 6. KPM runtime and patches
# Build the runtime and KMRP's module from their tracked sources, then package the
# patch. No game executable or prebuilt module is an input.
$kpmRuntimeDir = Join-Path $projectRoot "build\kpm-runtime"
$kpmSubmodule = Join-Path $projectRoot "third_party\Kotor-Patch-Manager"
if (-not (Test-Path -LiteralPath (Join-Path $kpmSubmodule "src\KotorPatcher\src\core\patcher.cpp"))) {
    throw "KOTOR Patch Manager is missing at $kpmSubmodule. Run: git submodule update --init"
}
$nativeDir = Join-Path $projectRoot "build\native-runtime"
$nativePack = Join-Path $nativeDir "kmrp-assets.pack"
$kpmDir = Join-Path $buildDir "kpm-patches"
$kpmConfigDir = Join-Path $buildDir "kpm-config"
$controllerName = "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch"
$controllerDist = Join-Path $distDir "controller"
$highFpsKpatch = Join-Path $projectRoot "third_party\Included\HighFpsFixes-1.0.1 by D3M0\HighFpsFixes.kpatch"
$emptyContainersKpatch = Join-Path $projectRoot "third_party\Included\K1MarkedEmptyContainers-1.0.0 by ShaeMyName\K1MarkedEmptyContainers.kpatch"
$driverCompatKpatch = Join-Path $projectRoot "third_party\Included\k1-modern-driver-compatibility-2.0.1 by Synchro\k1-modern-driver-compatibility.kpatch"

# Cached like the resources (2026-11-01, the maintainer asked): this step took 80 to 140
# seconds of a two-minute build, and it ran when only the installer's C# had changed. It
# reads what is listed here and not src\patcher, whose source is compiled in step 7; the
# folders were traced from the imports of the tools it runs and the scripts it calls,
# and neither those tools nor the module's source read the clock or, bar KMRP_TEXTURE_PACK,
# the environment. What the compiled files depend on, and where each is counted:
#   sources, headers, the build scripts and so every compiler and linker flag, the .def
#   and hook tables   their files' contents ($moduleSources)
#   what is generated from those   the tools that do it (tools\, by code) and step 2's output
#   dependencies   SDL3 (build\deps), third_party, the art, the fonts, the texture pack
#   the compiler   the versions, paths and option variables tools\toolchain_identity.cmd
#                  prints, and the hashes of cl, link and the compiler's own DLLs
#   Python         its version and every installed package's
# Its output counts too: the stamp holds a hash of everything the step makes, so a module
# built by hand or swapped in for a test (build_native_runtime.cmd alone), or one a disk
# damaged, is never taken for this step's own. The stamp goes before the work starts, so a
# run that fails leaves none, even for inputs that are then put back.
# Test-BuildCache.ps1 changes each of these and compares a cached build with a clean one.
$moduleStamp = Join-Path $buildDir "modules.inputs.sha256"
$moduleOutputs = @(
    (Join-Path $kpmRuntimeDir "KotorPatcher.dll"), (Join-Path $kpmRuntimeDir "binkw32.dll"),
    (Join-Path $nativeDir "kmrp-native.dll"), $nativePack,
    (Join-Path $projectRoot "build\controller-standalone\kmrp-controller.dll"),
    (Join-Path $kpmDir "KMRP.kpatch"), (Join-Path $kpmDir $controllerName),
    (Join-Path $kpmDir "kmrp-controller.verification.json"),
    (Join-Path $kpmConfigDir "kmrp.hooks.toml"), (Join-Path $kpmConfigDir "kmrp-controller.hooks.toml"),
    (Join-Path $kpmConfigDir "high-fps-fixes.hooks.toml"), (Join-Path $kpmConfigDir "k1-marked-empty-containers.hooks.toml"),
    (Join-Path $kpmConfigDir "k1-modern-driver-compatibility.hooks.toml"),
    (Join-Path $controllerDist $controllerName), (Join-Path $controllerDist "verification.json"))
$toolchain = @(& cmd.exe /d /c (Join-Path $projectRoot "tools\toolchain_identity.cmd") 2>$null)
if ($LASTEXITCODE -ne 0) { throw "tools\toolchain_identity.cmd failed" }
$compilerFiles = New-Object System.Collections.Generic.List[string]
foreach ($line in $toolchain) {
    if ($line -notmatch '\\(cl|link)\.exe$') { continue }
    $compilerFiles.Add($line)
    foreach ($part in @("c1.dll", "c1xx.dll", "c2.dll")) {
        $compilerFile = Join-Path (Split-Path -Parent $line) $part
        if (Test-Path -LiteralPath $compilerFile) { $compilerFiles.Add($compilerFile) }
    }
}
if ($compilerFiles.Count -lt 2) { throw "tools\toolchain_identity.cmd named no compiler" }
$pythonPackages = (& $Python -c "import importlib.metadata as m; print(sorted(d.name + '==' + d.version for d in m.distributions()))" 2>$null) -join " "
# By content, not by size and time: a file put back with its old time still counts.
$moduleSources = New-Object System.Collections.Generic.List[string]
foreach ($folder in @("src\controller-native", "src\engine", "src\kpm-runtime", "macos\tools",
                      "third_party\Kotor-Patch-Manager\src\KotorPatcher", "third_party\Kotor-Patch-Manager\src\KProxy",
                      "third_party\lzma-sdk")) {
    foreach ($item in Get-ChildItem -LiteralPath (Join-Path $projectRoot $folder) -Recurse -File -Force) {
        $moduleSources.Add($item.FullName)
    }
}
$moduleFingerprint = Get-InputFingerprint -Paths (@($moduleSources) + @($compilerFiles) + @(
    (Join-Path $projectRoot "tools"), (Join-Path $projectRoot "assets"), (Join-Path $projectRoot "fonts"),
    (Join-Path $projectRoot "third_party"), (Join-Path $projectRoot "build-inputs"),
    (Join-Path $projectRoot "build\deps"), (Join-Path $projectRoot "build\fonts"),
    $resourceDir, $blendTable, $engineSource, $resolvedTexturePack,
    (Join-Path $projectRoot "LICENSE"), (Join-Path $projectRoot "THIRD_PARTY_NOTICES.md"),
    (Join-Path $projectRoot "build_kmrp.ps1"))) -Extra (@("python $pythonVersion", "packages $pythonPackages",
    "version $patchVersion") + $toolchain) `
    -Reach "build_windows_engine,build_native_engine,build_native_kpatch,build_native_assets,kmrp_pack,build_controller_assets,build_controller_kpatch,build_bundled_kpatch_config"
$modulesCurrent = (-not $FreshModules) -and (Test-Path -LiteralPath $moduleStamp -PathType Leaf)
foreach ($output in $moduleOutputs) {
    if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { $modulesCurrent = $false }
}
$moduleState = ""
if ($modulesCurrent) {
    $moduleState = $moduleFingerprint + " " + (Get-InputFingerprint -Paths $moduleOutputs)
    $modulesCurrent = Test-StepCurrent $moduleStamp $moduleState
}
foreach ($retiredKpmDir in @((Join-Path $distDir "KMRP for KPM"), (Join-Path $distDir "KPM patches"))) {
    if (Test-Path -LiteralPath $retiredKpmDir) { Remove-Item -LiteralPath $retiredKpmDir -Recurse -Force }
}
if ($modulesCurrent) {
    Write-Host "  [cached] Runtime, modules and patches: inputs and outputs unchanged" -ForegroundColor DarkGreen
} else {
Remove-Item -LiteralPath $moduleStamp -Force -ErrorAction SilentlyContinue
Start-Step "Building KOTOR Patch Manager's runtime and KMRP's patch"
Invoke-Tool -Exe "cmd.exe" -Label "runtime" -FailureMessage "Building KOTOR Patch Manager's runtime failed (src\kpm-runtime\build.cmd)" `
    -Arguments @("/c", (Join-Path $projectRoot "src\kpm-runtime\build.cmd"))

# KMRP's module, with the engine recipe inside it, and its art pack, every
# resolution's files, which the installer carries and writes beside it. The pack is
# rebuilt whenever the resources were (it is skipped only with -ReuseResources and a
# pack already there), since build_native_runtime.cmd itself builds one only when none
# exists. Until 2026-10-19 the art was a bank inside the module (native-assets.bin).
# The module's art pack (tools\build_native_assets.py, about three minutes) was deleted
# here on every build so the module script made it again. Now it is kept while
# everything it is made from is unchanged: the resolution archives and the blend table,
# the tools, the art, the helper's C source, the texture pack and the SDL3 build
# (2026-10-27). The fonts it makes for itself under build\native-runtime are not inputs.
$nativePackStamp = $nativePack + ".inputs.sha256"
$nativePackFingerprint = Get-InputFingerprint -Paths @(
    $resourceDir, $blendTable, (Join-Path $projectRoot "tools"), (Join-Path $projectRoot "assets"),
    (Join-Path $projectRoot "macos\tools"), $resolvedTexturePack, (Join-Path $projectRoot "build\deps")) `
    -Reach "build_native_assets,kmrp_pack" -Extra @("python $pythonVersion")
$nativePackCurrent = (Test-Path -LiteralPath $nativePack) -and (Test-StepCurrent $nativePackStamp $nativePackFingerprint)
if ($nativePackCurrent) {
    Write-Detail "the module's art pack: inputs unchanged, kept"
} elseif (Test-Path -LiteralPath $nativePack) {
    Remove-Item -LiteralPath $nativePack -Force
}
$textFontTexturePack = $env:KMRP_TEXTURE_PACK
try {
    $env:KMRP_TEXTURE_PACK = $resolvedTexturePack
    Invoke-Tool -Exe "cmd.exe" -Label "module" -FailureMessage "Building KMRP's module failed (src\controller-native\build_native_runtime.cmd)" `
        -Arguments @("/c", (Join-Path $projectRoot "src\controller-native\build_native_runtime.cmd"))
    if (Test-Path -LiteralPath $nativePack) {
        Set-Content -LiteralPath $nativePackStamp -Value $nativePackFingerprint -Encoding ascii
    }
} finally {
    $env:KMRP_TEXTURE_PACK = $textFontTexturePack
}

# KMRP's patch, KMRP.kpatch, for players who manage their patches with KOTOR Patch
# Manager, and the same patch's hooks as the installer writes them into
# patch_config.toml itself. The installer embeds both (step 7) and puts the .kpatch
# where KPM finds it (KpmEditionOperations.DeliverKpatches); its --export-kpm-patches
# writes it out for sharing. One patch since 2026-10-04; until then four, built by
# tools\build_kpatch.py (removed), with a data file and the Override files beside them.
New-Item -ItemType Directory -Force -Path $kpmDir | Out-Null
# The patch is this build's alone: an earlier build's files would sit beside it.
Get-ChildItem -LiteralPath $kpmDir -Filter "*.kpatch" -File | Remove-Item -Force
Get-ChildItem -LiteralPath $kpmConfigDir -Filter "*.toml" -File -ErrorAction SilentlyContinue | Remove-Item -Force
Invoke-Tool -Exe $Python -Label "kpatch" -FailureMessage "Building KMRP's patch failed" -Arguments @(
    (Join-Path $projectRoot "tools\build_native_kpatch.py"), "--module",
    (Join-Path $nativeDir "kmrp-native.dll"),
    "--out", $kpmDir, "--config-dir", $kpmConfigDir, "--version", $patchVersion)
# The controller patch, "KOTOR 1 Native Controller Mod + Xbox HUD", which the
# installer installs beside KMRP's patch while Controller Support is on: its module
# (assets, then the module), then the .kpatch into the same folder and its hooks beside
# KMRP's. It keeps its own version number: it is also released on its own.
Invoke-Tool -Exe "cmd.exe" -Label "controller module" -FailureMessage "Building the controller patch's module failed (src\controller-native\build_controller_standalone.cmd)" `
    -Arguments @("/c", (Join-Path $projectRoot "src\controller-native\build_controller_standalone.cmd"))
Invoke-Tool -Exe $Python -Label "controller kpatch" -FailureMessage "Building the controller patch failed" -Arguments @(
    (Join-Path $projectRoot "tools\build_controller_kpatch.py"),
    "--out", $kpmDir, "--config-dir", $kpmConfigDir)
# The same file is the standalone release, dist\controller, which
# Test-ControllerKpatch.py reads. Copied here so the two cannot differ: until
# 2026-10-08 dist\controller was written only by running the tool by hand, and a
# build left it holding an older patch than the installer carried.
New-Item -ItemType Directory -Force -Path $controllerDist | Out-Null
Copy-Item -LiteralPath (Join-Path $kpmDir $controllerName) -Destination (Join-Path $controllerDist $controllerName) -Force
Copy-Item -LiteralPath (Join-Path $kpmDir "kmrp-controller.verification.json") -Destination (Join-Path $controllerDist "verification.json") -Force
# D3M0's High FPS Fixes (MIT), carried as its author released it and installed only
# while High FPS Fix is on in Advanced Settings: its hooks as patch_config.toml blocks,
# after it has been held against both of KMRP's patches and the engine recipe.
Invoke-Tool -Exe $Python -Label "High FPS Fixes" -FailureMessage "The bundled High FPS Fixes patch cannot be installed beside KMRP" -Arguments @(
    (Join-Path $projectRoot "tools\build_bundled_kpatch_config.py"), $highFpsKpatch,
    "--config-dir", $kpmConfigDir, "--id", "high-fps-fixes")
# ShaeMyName's K1 Marked Empty Containers, the .kpatch as KOTOR Patch Manager 0.7.1's
# release ships it (KPM's repository, MIT), installed while Marked Empty Containers is
# on in Advanced Settings, the default (issue 43): one replace hook and no module, held
# against both of KMRP's patches and the engine recipe like the patch above.
Invoke-Tool -Exe $Python -Label "Marked Empty Containers" -FailureMessage "The bundled Marked Empty Containers patch cannot be installed beside KMRP" -Arguments @(
    (Join-Path $projectRoot "tools\build_bundled_kpatch_config.py"), $emptyContainersKpatch,
    "--config-dir", $kpmConfigDir, "--id", "k1-marked-empty-containers")
# Synchro's K1 Modern Driver Compatibility (MPL-2.0), the .kpatch as its author releases
# it, installed while Modern Driver Compatibility is on in Advanced Settings, the default:
# KOTOR Patch Manager's proxy loads it, so it needs no Wine override under Proton (issue
# 44). Until 2026-10-31 the installer wrote its standalone dinput8.dll and .asi instead,
# which it still does on Windows 7 and 8, with its author's build for them (step 7).
Invoke-Tool -Exe $Python -Label "Modern Driver Compatibility" -FailureMessage "The bundled K1 Modern Driver Compatibility patch cannot be installed beside KMRP" -Arguments @(
    (Join-Path $projectRoot "tools\build_bundled_kpatch_config.py"), $driverCompatKpatch,
    "--config-dir", $kpmConfigDir, "--id", "k1-modern-driver-compatibility")
$moduleState = $moduleFingerprint + " " + (Get-InputFingerprint -Paths $moduleOutputs)
Set-Content -LiteralPath $moduleStamp -Value $moduleState -Encoding ascii
Complete-Step
}

# ---------------------------------------------------------------- 7. the installer
Start-Step "Compiling the installer"
$engineArgs = @(
    "/resource:$(Join-Path $kpmRuntimeDir 'KotorPatcher.dll'),Kmrp.engine.runtime",
    "/resource:$(Join-Path $kpmRuntimeDir 'binkw32.dll'),Kmrp.engine.proxy",
    "/resource:$(Join-Path $kpmSubmodule 'LICENSE'),Kmrp.engine.license")
# The patch's hooks as patch_config.toml blocks: the ones always installed, and one
# file per option that has hooks of its own (KpmEditionOperations.PatchConfigSection).
$engineArgs += "/resource:$(Join-Path $kpmConfigDir 'kmrp.hooks.toml'),Kmrp.engine.hooks"
foreach ($optionHooks in (Get-ChildItem -LiteralPath $kpmConfigDir -Filter "kmrp.hooks.*.toml" -File)) {
    $option = $optionHooks.Name.Substring("kmrp.hooks.".Length, $optionHooks.Name.Length - "kmrp.hooks.".Length - ".toml".Length)
    $engineArgs += "/resource:$($optionHooks.FullName),Kmrp.engine.hooks.$option"
}
# The .kpatch itself, which also holds the module, and its README; the licence that
# goes with it is Kmrp.engine.license.
$kpatchPath = Join-Path $kpmDir "KMRP.kpatch"
if (-not (Test-Path -LiteralPath $kpatchPath)) { throw "tools\build_native_kpatch.py did not write $kpatchPath" }
$engineArgs += "/resource:$kpatchPath,Kmrp.kpatch"
# The art pack, which the installer writes into the game's patches folder beside the
# module (KpmEdition.cs, PackResource).
if (-not (Test-Path -LiteralPath $nativePack)) { throw "build_native_runtime.cmd did not write $nativePack" }
$engineArgs += "/resource:$nativePack,Kmrp.assets.pack"
$controllerKpatchPath = Join-Path $kpmDir "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch"
if (-not (Test-Path -LiteralPath $controllerKpatchPath)) { throw "tools\build_controller_kpatch.py did not write $controllerKpatchPath" }
$engineArgs += "/resource:$controllerKpatchPath,KmrpController.kpatch"
$engineArgs += "/resource:$(Join-Path $kpmConfigDir 'kmrp-controller.hooks.toml'),KmrpController.engine.hooks"
$engineArgs += "/resource:$highFpsKpatch,KmrpHighFps.kpatch"
$engineArgs += "/resource:$(Join-Path $kpmConfigDir 'high-fps-fixes.hooks.toml'),KmrpHighFps.engine.hooks"
$engineArgs += "/resource:$(Join-Path $projectRoot 'third_party\Included\HighFpsFixes-1.0.1 by D3M0\LICENSE'),Kmrp.license.highfps"
$engineArgs += "/resource:$emptyContainersKpatch,KmrpEmptyContainers.kpatch"
$engineArgs += "/resource:$(Join-Path $kpmConfigDir 'k1-marked-empty-containers.hooks.toml'),KmrpEmptyContainers.engine.hooks"
$engineArgs += "/resource:$(Join-Path $projectRoot 'third_party\Included\K1MarkedEmptyContainers-1.0.0 by ShaeMyName\LICENSE'),Kmrp.license.emptycontainers"
$engineArgs += "/resource:$driverCompatKpatch,KmrpDriverCompat.kpatch"
$engineArgs += "/resource:$(Join-Path $kpmConfigDir 'k1-modern-driver-compatibility.hooks.toml'),KmrpDriverCompat.engine.hooks"
$engineArgs += "/resource:$(Join-Path $projectRoot 'third_party\Included\k1-modern-driver-compatibility-2.0.1 by Synchro\LICENSE'),Kmrp.license.drivercompat"
# Its author's standalone build for Windows 7 and 8, where the .kpatch's module cannot run:
# written beside the game there instead (DriverCompatStandalone, InstallCore.cs).
$engineArgs += "/resource:$(Join-Path $projectRoot 'third_party\Included\k1-modern-driver-compatibility-2.0.1 by Synchro\standalone-win7\dinput8.dll'),Kmrp.drivercompat.win7.dinput8"
$engineArgs += "/resource:$(Join-Path $projectRoot 'third_party\Included\k1-modern-driver-compatibility-2.0.1 by Synchro\standalone-win7\k1-modern-driver-compatibility.asi'),Kmrp.drivercompat.win7.asi"
$engineArgs += "/resource:$(Join-Path $projectRoot 'src\patcher\KPM-PATCHES-README.txt'),Kmrp.kpatch.readme"
# The installer's embedded resources, one per line as "name<TAB>path", for the native Linux
# installer's build (tools/build_linux_installer.ps1), which embeds the same files under the
# same names (2026-10-30). One list, written from the arguments themselves: a resource added
# above reaches both installers.
$installerResources = Join-Path $projectRoot "build\kmrp\installer-resources.tsv"
$resourceLines = foreach ($argument in ($compilerArgs + $engineArgs)) {
    if ($argument -like "/resource:*") {
        $spec = $argument.Substring(10)
        $comma = $spec.LastIndexOf(",")
        "{0}`t{1}" -f $spec.Substring($comma + 1), [System.IO.Path]::GetFullPath($spec.Substring(0, $comma))
    }
}
[System.IO.File]::WriteAllLines($installerResources, [string[]]$resourceLines, (New-Object System.Text.UTF8Encoding $false))
Write-Detail ("{0} installer resources listed in {1}" -f @($resourceLines).Count, $installerResources)

Write-Bar -Percent 100 -Label "running the C# compiler"
Invoke-Tool -Exe $compiler -Arguments ($compilerArgs + $engineArgs) -Label "compile" `
    -FailureMessage "KMRP compilation failed"
Complete-Step ("{0:n1} MB" -f ((Get-Item $outputExe).Length / 1MB))

# ---------------------------------------------------------------- 8. finalise
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
Write-Host ("  build     {0} CEST, commit {1}{2}" -f $buildStamp.Substring(0, 16).Replace('T', ' '), $commitId,
    $(if ($uncommitted) { ", with uncommitted changes" } else { "" })) -ForegroundColor Gray
Write-Host ""
Write-Host "  KPM patches, inside the installer" -ForegroundColor Green
foreach ($file in @(Get-ChildItem -LiteralPath $kpmDir -File | Where-Object { $_.Extension -eq ".kpatch" })) {
    $kpmSha = [System.Security.Cryptography.SHA256]::Create()
    $kpmStream = [System.IO.File]::OpenRead($file.FullName)
    try { $kpmHash = [System.BitConverter]::ToString($kpmSha.ComputeHash($kpmStream)).Replace("-", "") }
    finally { $kpmStream.Dispose(); $kpmSha.Dispose() }
    Write-Host ("  {0,-34} {1,12:n0} bytes  {2}" -f $file.Name, $file.Length, $kpmHash) -ForegroundColor Gray
}
Write-Host ""
