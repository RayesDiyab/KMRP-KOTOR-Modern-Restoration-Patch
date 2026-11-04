<#
.SYNOPSIS
    build_kmrp.ps1 skips its module step only when nothing that step depends on has changed,
    and what a skipped build ships is what a clean build makes.

.DESCRIPTION
    The module step (the KPM runtime, both modules and their patches) is cached by a
    fingerprint of its inputs and a hash of its outputs. A stale module in a release would
    pass every other test, so each thing the fingerprint must notice is changed here in
    turn, a build is run, and the step's own line says whether it was skipped. Native
    compilation is judged by the build's log, and by whether the modules' file times moved.

      Skipped:  nothing changed; a C# file of the installer changed; a tool the step does
                not reach changed.
      Runs:     a header both modules share; a header in macos\tools; a build script (the
                compiler flags are there); the engine recipe's sites, which generate
                NativeEngine.generated.h; the hook table the .def is generated from; the CL
                variable; a module deleted; a module damaged at the same size and time.

    The tools a step reaches are not changed here: 63 of the 128 are reached by the interface
    resources too, the build tools among them, so one line would mean half an hour of
    rebuilding. tools\source_fingerprint.py --reach says what each step counts.

    Then the comparison: the step's folders moved aside and every output made from nothing,
    compared by SHA-256 with what the cached build had, then a cached build compared with
    that again, and the patches inside the installer compared by `--export-kpm-patches`.
    The installer's own file differs on every build, as this csc cannot compile
    deterministically, which is why its contents are what is compared.

    Every file changed is put back from a byte copy in a finally block. Takes about 15 minutes:
    only with `--group build` or `--only Test-BuildCache`, and no source may be edited
    during it (an edit during a build shipped a hook table naming a missing export, 2026-09-25).
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $projectRoot
$env:PATH = "C:\Program Files\dotnet;" + $env:PATH
$script:failures = 0
$installer = & (Join-Path $projectRoot "tools\kmrp_version.ps1") -WindowsInstaller
$nativeModule = Join-Path $projectRoot "build\native-runtime\kmrp-native.dll"
$controllerModule = Join-Path $projectRoot "build\controller-standalone\kmrp-controller.dll"
$stepFolders = @("build\native-runtime", "build\controller-standalone", "build\kpm-runtime",
                 "build\kmrp\kpm-patches", "build\kmrp\kpm-config", "dist\controller")
$aside = Join-Path $projectRoot "build\build-cache-test-aside"
$artifacts = @(
    "build\kpm-runtime\KotorPatcher.dll", "build\kpm-runtime\binkw32.dll",
    "build\native-runtime\kmrp-native.dll", "build\native-runtime\kmrp-assets.pack",
    "build\controller-standalone\kmrp-controller.dll",
    "build\kmrp\kpm-patches\KMRP.kpatch", "build\kmrp\kpm-patches\KOTOR 1 Native Controller Mod + Xbox HUD.kpatch",
    "build\kmrp\kpm-config\kmrp.hooks.toml", "build\kmrp\kpm-config\kmrp-controller.hooks.toml",
    "build\kmrp\kpm-config\high-fps-fixes.hooks.toml", "build\kmrp\kpm-config\k1-marked-empty-containers.hooks.toml",
    "build\kmrp\kpm-config\k1-modern-driver-compatibility.hooks.toml")

function Assert([bool]$condition, [string]$what) {
    if ($condition) { Write-Host "  PASS  $what" }
    else { Write-Host "  FAIL  $what" -ForegroundColor Red; $script:failures++ }
}

# Returns whether the step was skipped, after checking the build itself worked.
function Invoke-Build([string[]]$arguments = @()) {
    $clock = [Diagnostics.Stopwatch]::StartNew()
    $log = & (Join-Path $projectRoot "build_kmrp.ps1") -Plain @arguments *>&1 | ForEach-Object { "$_" }
    $skipped = [bool]($log | Select-String -SimpleMatch "[cached] Runtime, modules")
    $compiled = [bool]($log | Select-String -SimpleMatch "K1RuntimeEngine.cpp")
    Write-Host ("    built in {0:n0} s, module step {1}" -f $clock.Elapsed.TotalSeconds, $(if ($skipped) { "skipped" } else { "ran" }))
    if ($skipped -eq $compiled) { throw "The log says skipped=$skipped and compiled=$compiled." }
    foreach ($artifact in $artifacts) {
        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $artifact))) { throw "$artifact is missing after the build." }
    }
    return $skipped
}

function Get-Hashes {
    $hashes = [ordered]@{}
    foreach ($artifact in $artifacts) {
        $hashes[$artifact] = (Get-FileHash -LiteralPath (Join-Path $projectRoot $artifact) -Algorithm SHA256).Hash
    }
    return $hashes
}

function Compare-Hashes($expected, $actual, [string]$what) {
    $different = @($expected.Keys | Where-Object { $expected[$_] -ne $actual[$_] })
    Assert ($different.Count -eq 0) "$what ($($expected.Count) files): $($different -join ', ')"
}

# One line added to FILE for one build, and the file back as it was, byte for byte.
function Test-Change([string]$name, [string]$file, [string]$line, [bool]$expectSkipped) {
    $path = Join-Path $projectRoot $file
    $kept = [IO.File]::ReadAllBytes($path)
    try {
        [IO.File]::AppendAllText($path, "`n$line`n")
        $skipped = Invoke-Build
    }
    finally {
        [IO.File]::WriteAllBytes($path, $kept)
    }
    Assert ($skipped -eq $expectSkipped) "$name $(if ($expectSkipped) { 'skips the module step' } else { 'runs the module step' })"
}

try {
    Write-Host "A cached build changes nothing"
    Invoke-Build | Out-Null      # whatever state the last build left
    $start = Get-Hashes
    $nativeTime = (Get-Item -LiteralPath $nativeModule).LastWriteTimeUtc
    Assert (Invoke-Build) "nothing changed skips the module step"

    Write-Host "B a C#-only change skips native compilation"
    Test-Change "a C# file of the installer" "src\patcher\InstallPlatform.cs" "// build cache test" $true
    Test-Change "a tool no step reaches" "tools\build_release_shots.py" "BUILD_CACHE_TEST = 1" $true
    Assert ((Get-Item -LiteralPath $nativeModule).LastWriteTimeUtc -eq $nativeTime) "the module was not written"

    Write-Host "C what the binaries depend on runs it"
    Test-Change "a header both modules share" "src\controller-native\K1EngineMemory.h" "// build cache test" $false
    Test-Change "a C header in macos\tools" "macos\tools\kmrp-iconsize.h" "/* build cache test */" $false
    Test-Change "the module's build script, where its flags are" "src\controller-native\build_native_runtime.cmd" "rem build cache test" $false
    Test-Change "the runtime's build script" "src\kpm-runtime\build.cmd" "rem build cache test" $false
    Test-Change "the sites NativeEngine.generated.h is generated from" "src\engine\windows-sites.json" "" $false
    Test-Change "the hook table the exports are generated from" "src\controller-native\kotor1-native-runtime.hooks.toml" "# build cache test" $false

    Write-Host "D the compiler's options run it"
    $env:CL = "/DKMRP_BUILD_CACHE_TEST"
    try { Assert (-not (Invoke-Build)) "the CL variable runs the module step" }
    finally { Remove-Item Env:\CL }
    Assert (-not (Invoke-Build)) "and clearing it does"
    Assert (Invoke-Build) "then it is settled"

    Write-Host "E a bad output is not reused"
    Remove-Item -LiteralPath $nativeModule
    Assert (-not (Invoke-Build)) "a deleted module runs the module step"
    Assert ((Get-FileHash -LiteralPath $nativeModule -Algorithm SHA256).Hash -eq $start["build\native-runtime\kmrp-native.dll"]) "and makes it again"
    # One byte, the size and the time kept, as a failing disk would leave it.
    $time = (Get-Item -LiteralPath $controllerModule).LastWriteTimeUtc
    $bytes = [IO.File]::ReadAllBytes($controllerModule)
    $middle = [int][Math]::Floor($bytes.Length / 2)
    $bytes[$middle] = $bytes[$middle] -bxor 0xFF
    [IO.File]::WriteAllBytes($controllerModule, $bytes)
    (Get-Item -LiteralPath $controllerModule).LastWriteTimeUtc = $time
    Assert (-not (Invoke-Build)) "a damaged module runs the module step"
    Assert ((Get-FileHash -LiteralPath $controllerModule -Algorithm SHA256).Hash -eq $start["build\controller-standalone\kmrp-controller.dll"]) "and makes it again"

    Write-Host "F a clean build makes what the cached build has"
    Assert (Invoke-Build) "the cached build is settled"
    $cached = Get-Hashes
    if (Test-Path -LiteralPath $aside) { throw "$aside is left from a run that stopped: look in it, then remove it." }
    New-Item -ItemType Directory -Path $aside | Out-Null
    foreach ($folder in $stepFolders) {
        $target = Join-Path $aside ($folder -replace '\\', '_')
        Move-Item -LiteralPath (Join-Path $projectRoot $folder) -Destination $target
    }
    Remove-Item -LiteralPath (Join-Path $projectRoot "build\kmrp\modules.inputs.sha256") -Force
    Assert (-not (Invoke-Build)) "with the step's folders gone it runs"
    $clean = Get-Hashes
    Compare-Hashes $cached $clean "the clean build's files are the cached build's"
    Assert (Invoke-Build) "the next build is cached"
    Compare-Hashes $clean (Get-Hashes) "and leaves them as they are"
    $exported = Join-Path $aside "exported"
    New-Item -ItemType Directory -Path $exported | Out-Null
    $process = Start-Process -FilePath $installer -ArgumentList @("--export-kpm-patches", "`"$exported`"") -Wait -PassThru
    Assert ($process.ExitCode -eq 0) "the cached installer gives up its patches"
    foreach ($name in "KMRP.kpatch", "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch") {
        Assert ((Get-FileHash -LiteralPath (Join-Path $exported $name) -Algorithm SHA256).Hash -eq
                $clean["build\kmrp\kpm-patches\$name"]) "the cached installer carries the clean $name"
    }
    # What the build does not make again goes back, and the folder only then.
    if ($script:failures -eq 0) {
        foreach ($folder in $stepFolders) {
            $from = Join-Path $aside ($folder -replace '\\', '_')
            $into = Join-Path $projectRoot $folder
            foreach ($item in Get-ChildItem -LiteralPath $from -Recurse -File -Force) {
                $there = Join-Path $into $item.FullName.Substring($from.Length + 1)
                if (-not (Test-Path -LiteralPath $there)) {
                    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $there) | Out-Null
                    Move-Item -LiteralPath $item.FullName -Destination $there
                }
            }
        }
        Remove-Item -LiteralPath $aside -Recurse -Force
    }
}
catch {
    Write-Host "  FAIL  $($_.Exception.Message)" -ForegroundColor Red
    $script:failures++
}

if ($script:failures -gt 0) {
    Write-Host "FAILED ($($script:failures))" -ForegroundColor Red
    exit 1
}
Write-Host "PASSED" -ForegroundColor Green
exit 0
