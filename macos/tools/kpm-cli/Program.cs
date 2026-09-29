// kpm-cli: drives KotOR Patch Manager's own KPatchCore library from the command line.
//   kpm-cli validate <kpatch> <KOTOR_Exe>   parse the patch the way the manager does and
//                                           run its hook and parameter validators (read-only)
//   kpm-cli stage <kpatch> <KOTOR_Exe> <dir> lay out <dir> exactly as an install lays out the
//                                           game folder (patches/<id>.dylib + patch_config.toml,
//                                           written by KPM's own ConfigGenerator), without
//                                           touching the executable
using KPatchCore.Managers;
using KPatchCore.Models;
using KPatchCore.Validators;
using System.Security.Cryptography;

if (args.Length >= 4 && args[0] == "stage") return Stage(args[1], args[2], args[3]);
if (args.Length >= 4 && args[0] == "stage-many") return StageMany(args[1], args[2], args.Skip(3).ToArray());
if (args.Length < 3 || args[0] != "validate") { Console.Error.WriteLine("usage: kpm-cli validate <kpatch> <game exe> | stage <kpatch> <game exe> <dir>"); return 2; }
string kpatch = Path.GetFullPath(args[1]), exe = args[2];
string sha = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(exe)));
Console.WriteLine($"game SHA-256 {sha[..16]}...");

var repo = new PatchRepository(Path.GetDirectoryName(kpatch)!);
var loaded = repo.LoadPatch(kpatch);
if (!loaded.Success || loaded.Data is null) { Console.WriteLine($"LoadPatch FAILED: {loaded.Error}"); return 1; }
var id = loaded.Data.Manifest.Id;
Console.WriteLine($"patch {id} v{loaded.Data.Manifest.Version}: manifest {(PatchValidator.ValidateManifest(loaded.Data.Manifest).Success ? "ok" : "INVALID")}");

var scan = repo.ScanPatches();
var hooks = repo.LoadHooksForVersion(id, sha);
if (!hooks.Success || hooks.Data is null) { Console.WriteLine($"LoadHooksForVersion FAILED: {hooks.Error}"); return 1; }
Console.WriteLine($"{hooks.Data.Count} hooks for this game version: " +
    string.Join(", ", hooks.Data.GroupBy(h => h.Type).Select(g => $"{g.Count()} {g.Key}")));

int bad = 0;
var v = HookValidator.ValidateHooks(hooks.Data);
Console.WriteLine($"ValidateHooks: {(v.Success ? "ok" : "FAILED " + v.Error)}"); if (!v.Success) bad++;
var p = HookValidator.ValidateParameterSources(new Dictionary<string, List<Hook>> { [id] = hooks.Data }, Architecture.x86_64);
Console.WriteLine($"ValidateParameterSources(x64): {(p.Success ? "ok" : "FAILED " + p.Error)}"); if (!p.Success) bad++;
var o = HookValidator.DetectOverlappingHooks(hooks.Data);
Console.WriteLine($"DetectOverlappingHooks: {(o.Count == 0 ? "none" : string.Join("; ", o))}"); if (o.Count > 0) bad++;
return bad == 0 ? 0 : 1;

// stage-many <KOTOR_Exe> <dir> <kpatch>...: like stage, for several patches in one config, in
// the order given (KotorPatcher applies them in that order). Also runs KPM's overlap check
// across all of them, which per-patch validation cannot see.
static int StageMany(string exe, string dir, string[] kpatches)
{
    Directory.CreateDirectory(Path.Combine(dir, "patches"));
    var version = KPatchCore.Detectors.GameDetector.DetectVersion(exe);
    if (!version.Success || version.Data is null) { Console.WriteLine($"DetectVersion FAILED: {version.Error}"); return 1; }
    Console.WriteLine($"game: {version.Data}");
    var config = new PatchConfig { TargetVersionSha = version.Data.Hash };
    var all = new List<Hook>();
    foreach (string kpatchArg in kpatches)
    {
        string kpatch = Path.GetFullPath(kpatchArg);
        var repo = new PatchRepository(Path.GetDirectoryName(kpatch)!);
        var loaded = repo.LoadPatch(kpatch);
        if (!loaded.Success || loaded.Data is null) { Console.WriteLine($"LoadPatch FAILED: {loaded.Error}"); return 1; }
        repo.ScanPatches();
        string id = loaded.Data.Manifest.Id;
        var hooks = repo.LoadHooksForVersion(id, version.Data.Hash);
        if (!hooks.Success || hooks.Data is null) { Console.WriteLine($"{id}: hooks FAILED: {hooks.Error}"); return 1; }
        var runtimeHooks = hooks.Data.Where(h => h.Type != HookType.Static).ToList();
        string dll = string.Empty;
        // A module is loaded for DETOUR hooks, and for a patch with no hooks at all (DLL_ONLY:
        // its module does its own work when loaded), as KPM's PatchApplicator extracts it.
        if (hooks.Data.Count == 0 || runtimeHooks.Any(h => h.Type == HookType.Detour))
        {
            var ex = repo.ExtractPatchDll(id, Path.Combine(dir, "patches"), version.Data);
            if (!ex.Success || ex.Data is null) { Console.WriteLine($"{id}: extract FAILED: {ex.Error}"); return 1; }
            dll = Path.GetRelativePath(dir, ex.Data);
        }
        config.AddPatch(id, dll, runtimeHooks);
        all.AddRange(hooks.Data);
        Console.WriteLine($"staged {id}: {runtimeHooks.Count} runtime hooks, module '{dll}'");
    }
    var overlaps = HookValidator.DetectOverlappingHooks(all);
    Console.WriteLine($"DetectOverlappingHooks (all patches): {(overlaps.Count == 0 ? "none" : string.Join("; ", overlaps))}");
    if (overlaps.Count > 0) return 1;
    var written = KPatchCore.Applicators.ConfigGenerator.GenerateConfigFile(config, Path.Combine(dir, "patch_config.toml"));
    Console.WriteLine($"config {(written.Success ? "written" : "FAILED " + written.Error)}");
    return written.Success ? 0 : 1;
}

static int Stage(string kpatchArg, string exe, string dir)
{
    string kpatch = Path.GetFullPath(kpatchArg);
    Directory.CreateDirectory(Path.Combine(dir, "patches"));
    var version = KPatchCore.Detectors.GameDetector.DetectVersion(exe);
    if (!version.Success || version.Data is null) { Console.WriteLine($"DetectVersion FAILED: {version.Error}"); return 1; }
    Console.WriteLine($"game: {version.Data}");
    var repo = new PatchRepository(Path.GetDirectoryName(kpatch)!);
    var loaded = repo.LoadPatch(kpatch);
    if (!loaded.Success || loaded.Data is null) { Console.WriteLine($"LoadPatch FAILED: {loaded.Error}"); return 1; }
    repo.ScanPatches();
    string id = loaded.Data.Manifest.Id;
    var hooks = repo.LoadHooksForVersion(id, version.Data.Hash);
    if (!hooks.Success || hooks.Data is null) { Console.WriteLine($"hooks FAILED: {hooks.Error}"); return 1; }
    var runtimeHooks = hooks.Data.Where(h => h.Type != HookType.Static).ToList();
    string dll = string.Empty;
    if (hooks.Data.Count == 0 || runtimeHooks.Any(h => h.Type == HookType.Detour))  // DLL_ONLY, or detours
    {
        var ex = repo.ExtractPatchDll(id, Path.Combine(dir, "patches"), version.Data);
        if (!ex.Success || ex.Data is null) { Console.WriteLine($"extract FAILED: {ex.Error}"); return 1; }
        dll = Path.GetRelativePath(dir, ex.Data);
    }
    var config = new PatchConfig { TargetVersionSha = version.Data.Hash };
    config.AddPatch(id, dll, runtimeHooks);
    var written = KPatchCore.Applicators.ConfigGenerator.GenerateConfigFile(config, Path.Combine(dir, "patch_config.toml"));
    Console.WriteLine($"staged {id}: {runtimeHooks.Count} runtime hooks, module '{dll}', config {(written.Success ? "written" : "FAILED " + written.Error)}");
    return written.Success ? 0 : 1;
}
