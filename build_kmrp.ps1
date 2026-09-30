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
    [string]$GoldExe = ".\build\kmrp\swkotor_gold_v24_movieaspect.exe",
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
$patchResource = Join-Path $buildDir "gold.kup"
$outputExe = Join-Path $distDir ($OutputName + ".exe")

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
# Two more since 2026-09-28: the KPM relocation table and the KPM edition; one
# more since 2026-09-29, KOTOR Patch Manager's runtime and KMRP's patches, and one
# fewer the same day, when KMRP for KPM became part of the one installer.
$script:StepTotal = if ($ReuseResources) { 8 } else { 9 }
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
$resolvedBundled = @($BundledOverride | ForEach-Object { (Resolve-Path -LiteralPath (Resolve-InputPath $_)).Path })

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
    $fontScaleSets = Join-Path $projectRoot "build\fonts"
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
    Complete-Step ("{0} resolution archives" -f $archives.Count)
} else {
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
Start-Step "Pooling the resolution layouts"
$layoutPool = Join-Path $buildDir "resolution-layouts.zip"
Invoke-Tool -Exe $Python -Label "pool" -FailureMessage "Pooling the resolution layouts failed" -Arguments @(
    (Join-Path $projectRoot "tools\pack_resolution_layouts.py"), $resourceDir, $layoutPool)
Complete-Step ("{0:n1} MB" -f ((Get-Item $layoutPool).Length / 1MB))

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

# ---------------------------------------------------------------- 4b. KPM relocations
# The KPM edition cannot put gold's eleven appended sections back at their own
# addresses, so its module moves them and re-points every address that names
# them. tools/kpm_relocations.py finds those addresses in gold by two independent
# methods, stops the build if they disagree, and proves the table by moving the
# code. Both editions embed it (Kmrp.kpm.relocations): the KPM edition installs
# from it, and the standalone can write a data file for tests.
Start-Step "Computing the KPM relocation table"
$kpmRelocations = Join-Path $buildDir "kpm-relocations.txt"
Invoke-Tool -Exe $Python -Label "relocations" -FailureMessage "The KPM relocation table could not be proved" -Arguments @(
    (Join-Path $projectRoot "tools\kpm_relocations.py"), "--gold", $resolvedGold,
    "--clean", $resolvedSource, "--out", $kpmRelocations)
Complete-Step ("{0} fields" -f @(Get-Content -LiteralPath $kpmRelocations | Where-Object { $_ -match "^[A-Z]" }).Count)

# ---------------------------------------------------------------- 5. compiler arguments
# What the installer embeds; step 7 compiles it from these.
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
    "/resource:$(Join-Path $resourceDir 'bundled-override.txt'),Kmrp.bundled",
    "/resource:$(Join-Path $projectRoot 'src\patcher\brand.png'),Kmrp.brand",
    "/resource:$(Join-Path $resourceDir 'GPL-3.0-KOTOR-High-Resolution-Menus.txt'),Kmrp.license.highresolutionmenus",
    # The bundled K1 Modern Driver Compatibility standalone build (Synchro, MPL-2.0),
    # written into the game folder when the user leaves that option on. Two files, and
    # neither touches swkotor.exe -- see docs/third-party-driver-compat.md.
    "/resource:$(Join-Path $projectRoot 'third_party\Included\k1-modern-driver-compatibility-1.2.0 by Synchro\dinput8.dll'),Kmrp.drivercompat.dinput8",
    "/resource:$(Join-Path $projectRoot 'third_party\Included\k1-modern-driver-compatibility-1.2.0 by Synchro\k1-modern-driver-compatibility.asi'),Kmrp.drivercompat.asi",
    "/resource:$(Join-Path $projectRoot 'third_party\Included\k1-modern-driver-compatibility-1.2.0 by Synchro\LICENSE'),Kmrp.license.drivercompat"
    # KMRP's module, from src/controller-native/, which is what build.cmd there
    # produces: KMRP's native path plus Saul0097's author-approved sources as
    # modified by KMRP (vendor/, MIT; see THIRD_PARTY_NOTICES.md). KMRP's installer
    # installs it as each of its KPM patches' module, and the .kpatch files carry
    # it too.
    #
    # Until 2026-09-29 this list also embedded kmrp-controller-runtime.asi, a
    # statically linked KPM runtime from Saul0097's package that K1DC's ASI loader
    # loaded, and KPM's licence from the same folder. The runtime is built from the
    # submodule now (step 6, Kmrp.engine.*).
    "/resource:$(Join-Path $projectRoot 'src\controller-native\kmrp-controller.module'),Kmrp.controller.module"
    "/resource:$(Join-Path $projectRoot 'build\deps\kmrp-sdl3.dll'),Kmrp.controller.sdl"
    "/resource:$(Join-Path $projectRoot 'build\deps\SDL3-3.4.16\LICENSE.txt'),Kmrp.controller.sdllicense"
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
$compilerArgs += "/resource:$layoutPool,Kmrp.override.layouts"
$compilerArgs += "/resource:$kpmRelocations,Kmrp.kpm.relocations"
$compilerArgs += "/resource:$blendResource,Kmrp.guiblend"

$compilerArgs += (Join-Path $projectRoot "src\patcher\KmrpPatcher.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\AbilityIconGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\GameArtGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\ControllerPromptGenerator.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\AssemblyInfo.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\KpmEdition.cs")
$compilerArgs += (Join-Path $projectRoot "src\patcher\GuiBlend.cs")

# Properties -> Details must name the version the install record names. The two live
# in different files and nothing compares them at run time, so they drifted twice:
# the v2.10.0 release reported 2.7.0, and 2.11.0-movieaspect was built reporting
# 2.10.0-mapnotes. Refuse to compile while they disagree.
$patchVersion = [regex]::Match(
    (Get-Content -Raw -LiteralPath (Join-Path $projectRoot "src\patcher\KmrpPatcher.cs")),
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
    throw ("Version mismatch: PatchVersion '{0}' in KmrpPatcher.cs, but AssemblyInfo.cs has " +
        "AssemblyVersion '{1}', AssemblyFileVersion '{2}', AssemblyInformationalVersion '{3}' " +
        "(expected '{4}', '{4}', '{0}').") -f $patchVersion, $versionFields["AssemblyVersion"],
        $versionFields["AssemblyFileVersion"], $versionFields["AssemblyInformationalVersion"], $numericVersion
}
Write-Host ("    version {0}, matching Properties -> Details" -f $patchVersion) -ForegroundColor DarkGray

# ---------------------------------------------------------------- 6. KPM runtime and patches
# Since 2026-09-29 the installer installs through KMRP's four KPM patches, with
# KOTOR Patch Manager's runtime or for KPM itself. This step makes everything it
# embeds that is not interface art: the runtime and its binkw32.dll proxy, from
# the submodule (src\kpm-runtime\build.cmd); the unmodified executable's bytes the
# data file is built from (Kmrp.kpm.originals: Steam's swkotor.exe is encrypted on
# disk, so the installer never reads them from the player's file); and the
# patches, as .kpatch files for KOTOR Patch Manager and as patch_config.toml
# sections for the installer, from one hook table.
Start-Step "Building KOTOR Patch Manager's runtime and KMRP's patches"
$kpmRuntimeDir = Join-Path $projectRoot "build\kpm-runtime"
$kpmSubmodule = Join-Path $projectRoot "third_party\Kotor-Patch-Manager"
if (-not (Test-Path -LiteralPath (Join-Path $kpmSubmodule "src\KotorPatcher\src\core\patcher.cpp"))) {
    throw "KOTOR Patch Manager is missing at $kpmSubmodule. Run: git submodule update --init"
}
Invoke-Tool -Exe "cmd.exe" -Label "runtime" -FailureMessage "Building KOTOR Patch Manager's runtime failed (src\kpm-runtime\build.cmd)" `
    -Arguments @("/c", (Join-Path $projectRoot "src\kpm-runtime\build.cmd"))

# The fields ResolutionPatch handles, which the originals must cover, listed by
# ResolutionPatch itself: a small build of the installer's code with only the two
# resources that listing reads.
$sitesExe = Join-Path $buildDir "kmrp-sites.exe"
Invoke-Tool -Exe $compiler -Label "compile" -FailureMessage "Compiling the resolution-site lister failed" -Arguments @(
    "/nologo", "/optimize+", "/target:exe", "/platform:anycpu", "/out:$sitesExe",
    "/reference:System.dll", "/reference:System.Drawing.dll",
    "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll",
    "/reference:System.Windows.Forms.dll",
    "/resource:$patchResource,Kmrp.goldpatch",
    "/resource:$(Join-Path $resourceDir 'resolutions.tsv'),Kmrp.resolutions",
    (Join-Path $projectRoot "src\patcher\KmrpPatcher.cs"),
    (Join-Path $projectRoot "src\patcher\AbilityIconGenerator.cs"),
    (Join-Path $projectRoot "src\patcher\GameArtGenerator.cs"),
    (Join-Path $projectRoot "src\patcher\ControllerPromptGenerator.cs"),
    (Join-Path $projectRoot "src\patcher\AssemblyInfo.cs"),
    (Join-Path $projectRoot "src\patcher\KpmEdition.cs"),
    (Join-Path $projectRoot "src\patcher\GuiBlend.cs"))
$kpmSites = Join-Path $buildDir "kpm-resolution-sites.txt"
Invoke-Tool -Exe $sitesExe -Label "sites" -FailureMessage "Listing the resolution fields failed" -Arguments @(
    "--kpm-sites", $resolvedSource, $kpmSites)
$kpmOriginals = Join-Path $buildDir "kpm-originals.bin"
Invoke-Tool -Exe $Python -Label "originals" -FailureMessage "The KPM originals could not be proved" -Arguments @(
    (Join-Path $projectRoot "tools\kpm_originals.py"), "--clean", $resolvedSource,
    "--delta", $patchResource, "--relocations", $kpmRelocations, "--sites", $kpmSites,
    "--out", $kpmOriginals)

# KMRP's .kpatch files, for players who manage their patches with KOTOR Patch
# Manager. The installer embeds them (step 7) and puts them where KPM finds them
# (KpmEditionOperations.DeliverKpatches), so dist\ is the installer alone; its
# --export-kpm-patches writes them out for sharing. Until 2026-09-29 they came in
# dist\KMRP for KPM\ with an installer of their own, compiled with KPM_EDITION, and
# then, later that day, in dist\KPM patches\; both folders are removed, so no stale
# copy ships.
$kpmDir = Join-Path $buildDir "kpm-patches"
New-Item -ItemType Directory -Force -Path $kpmDir | Out-Null
foreach ($retiredKpmDir in @((Join-Path $distDir "KMRP for KPM"), (Join-Path $distDir "KPM patches"))) {
    if (Test-Path -LiteralPath $retiredKpmDir) { Remove-Item -LiteralPath $retiredKpmDir -Recurse -Force }
}
# The set of patches is this build's alone: an earlier build's (two until
# 2026-09-28) would sit beside it, fail the check and offer players a patch that
# no longer exists.
Get-ChildItem -LiteralPath $kpmDir -Filter "*.kpatch" -File | Remove-Item -Force
$kpmConfigDir = Join-Path $buildDir "kpm-config"
# The patches: the tracked hook sets and the module src\controller-native\build.cmd
# produced, checked against KPM 0.7.1's install rules, and each one's config
# section checked against its .kpatch (tools/build_kpatch.py).
Invoke-Tool -Exe $Python -Label "kpatch" -FailureMessage "Building KMRP's patches failed" -Arguments @(
    (Join-Path $projectRoot "tools\build_kpatch.py"), "--module",
    (Join-Path $projectRoot "src\controller-native\kmrp-controller.module"),
    "--out", $kpmDir, "--config-dir", $kpmConfigDir,
    "--resolutions", (Join-Path $resourceDir "resolutions.tsv"), "--version", $patchVersion)
Complete-Step

# ---------------------------------------------------------------- 7. the installer
Start-Step "Compiling the installer"
$compilerArgs += "/resource:$kpmOriginals,Kmrp.kpm.originals"
$engineArgs = @(
    "/resource:$(Join-Path $kpmRuntimeDir 'KotorPatcher.dll'),Kmrp.engine.runtime",
    "/resource:$(Join-Path $kpmRuntimeDir 'binkw32.dll'),Kmrp.engine.proxy",
    "/resource:$(Join-Path $kpmSubmodule 'LICENSE'),Kmrp.engine.license")
foreach ($patchId in @("kmrp", "kmrp-controller", "kmrp-movies", "kmrp-map-notes")) {
    $engineArgs += "/resource:$(Join-Path $kpmConfigDir ($patchId + '.toml')),Kmrp.engine.config.$patchId"
}
# The .kpatch files themselves, and their README; the licence that goes with them is
# Kmrp.engine.license. File names as tools/build_kpatch.py writes them, in the same
# pairs as KpmEditionOperations.Kpatches.
foreach ($kpatch in @(@("kmrp", "KMRP.kpatch"), @("kmrp-controller", "KMRP Controller.kpatch"),
        @("kmrp-movies", "KMRP Movies.kpatch"), @("kmrp-map-notes", "KMRP Map Notes.kpatch"))) {
    $kpatchPath = Join-Path $kpmDir $kpatch[1]
    if (-not (Test-Path -LiteralPath $kpatchPath)) { throw "tools\build_kpatch.py did not write $kpatchPath" }
    $engineArgs += "/resource:$kpatchPath,Kmrp.kpatch.$($kpatch[0])"
}
$engineArgs += "/resource:$(Join-Path $projectRoot 'src\patcher\KPM-PATCHES-README.txt'),Kmrp.kpatch.readme"
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
