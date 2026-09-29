using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;

namespace Kmrp
{
    /// <summary>KMRP's install, on KOTOR Patch Manager's runtime.
    ///
    /// KMRP's installer does not rewrite swkotor.exe: the executable changes are
    /// KMRP's four KPM patches (tools/build_kpatch.py), whose core module applies
    /// them in memory when the game starts (src/controller-native/K1KpmApplier.cpp)
    /// from kmrp-kpm.dat, which this writes -- the Movies and Map Notes parts only
    /// when those patches are installed. That is what lets one installer serve both
    /// the editable CD 1.03 swkotor.exe and Steam's, whose DRM refuses a changed
    /// file. It installs one of two ways, chosen per install (ManagedByPatchManager):
    ///
    ///   On its own, it installs KOTOR Patch Manager's runtime itself, as KPM's
    ///   proxy deployment lays out a game folder (src/kpm-runtime/README.md): the
    ///   proxy as binkw32.dll, the game's own renamed binkw32Hooked.dll,
    ///   KotorPatcher.dll, patch_config.toml and the modules in patches\. The player
    ///   then starts the game as always, from Steam or from swkotor.exe. On CD 1.03
    ///   it also sets the large-address flag, the one bit of swkotor.exe it changes,
    ///   leaving KPM a backup of the unmodified file (WriteKpmBackup).
    ///
    ///   For KOTOR Patch Manager -- when KPM's runtime is already in the game folder,
    ///   or the player chose it in Advanced Settings -- it installs everything but
    ///   the patches, and the player ticks KMRP's .kpatch files in KPM. Until
    ///   2026-09-29 this was a separate installer, KMRP for KPM, compiled from this
    ///   source with KPM_EDITION.
    ///
    /// Either way it replaces an install by the standalone installer, which until
    /// 2026-09-29 wrote the gold delta into swkotor.exe
    /// (PatchOperations.RestoreStandalone), and its own earlier install, of either
    /// kind.
    ///
    /// The data file is derived, not restated: the final image is built as the
    /// standalone installer builds it -- the unmodified executable, the embedded gold
    /// delta, ResolutionPatch for the chosen resolution, the map-note flag on
    /// (GoldPatch.ApplyToOriginals) -- from the unmodified executable's bytes this
    /// installer carries rather than the player's file, so that Steam's swkotor.exe,
    /// encrypted on disk, is served the same way as CD 1.03. The file records only
    /// how that differs from the unmodified executable, plus the eleven appended
    /// sections and the relocation table tools/kpm_relocations.py computed from gold,
    /// each change tagged with the patch it belongs to. So with all four patches the
    /// two editions run the same bytes and cannot drift apart.
    ///
    /// Everything else is shared with the standalone installer's code: Override files,
    /// swkotor.ini, DPI and NVIDIA settings, and on its own K1 Modern Driver
    /// Compatibility (DriverCompatOperations). For KOTOR Patch Manager it leaves K1DC
    /// to KPM, where Synchro's K1DC is a .kpatch of its own.</summary>
    internal static class KpmEditionOperations
    {
        internal const string DataName = "kmrp-kpm.dat";
        internal const string ManifestName = "KMRP_KPM.manifest";

        // KOTOR Patch Manager's runtime, laid out as its proxy deployment lays out a
        // game folder (KPatchCore KProxyInstaller and PatchApplicator): the game loads
        // the proxy as binkw32.dll, the proxy loads KotorPatcher.dll, and that reads
        // patch_config.toml and loads the modules under patches\. build.cmd in
        // src/kpm-runtime builds both DLLs from the submodule.
        private const string RuntimeName = "KotorPatcher.dll";
        private const string ConfigName = "patch_config.toml";
        private const string BinkName = "binkw32.dll";
        private const string BinkMovedName = "binkw32Hooked.dll";
        private const string PatchFolder = "patches";
        private const string KpmLicenseName = "kmrp-kotor-patch-manager-LICENSE.txt";
        // KOTOR Patch Manager's own record of which game an executable was before a
        // patch changed it (KPatchCore InstallStateManager, ManagedInstallState).
        private const string KpmStateName = "kpm_install_state.json";
        // KOTOR Patch Manager's backup of an executable, named as its BackupManager
        // names one: <exe>.backup.<yyyyMMdd_HHmmss>, with <that>.json beside it.
        private const string KpmBackupInfix = ".backup.";
        // KMRP's patches in the order the config lists them: the core first, whose
        // module applies kmrp-kpm.dat as it loads, before any other patch's hooks go
        // in; the controller last, so a hook of its that fails -- KotorPatcher stops
        // at the first -- cannot keep the others out. Each one's config section is
        // tools/build_kpatch.py's, from the same hook table as its .kpatch.
        private static readonly string[] EnginePatches =
            { "kmrp", "kmrp-movies", "kmrp-map-notes", "kmrp-controller" };
        private const string RelocationResource = "Kmrp.kpm.relocations";
        // CD 1.03's bytes under gold's chunks, at the relocated fields and under every
        // field ResolutionPatch handles (tools/kpm_originals.py): what the data file is
        // built from, for CD 1.03 and Steam's swkotor.exe alike, since Steam's is
        // encrypted on disk.
        private const string OriginalsResource = "Kmrp.kpm.originals";
        private const long SteamLength = 4395008;
        private const uint BlockVa = 0x0086D000;
        private const int BlockSize = 0xB000;
        private const int BlockSections = 11;
        private const uint KindIn = 1, KindOut = 2, KindAbs = 3;

        // KMRP's SDL for PlayStation, Switch and Steam Deck pads, and its licence: KPM
        // extracts only a patch's module, so these go beside the game, where the module
        // looks for them (K1ControllerBackend.cpp).
        private static readonly string[] SupportResources = { "Kmrp.controller.sdl", "Kmrp.controller.sdllicense" };
        private static readonly string[] SupportFiles = { "kmrp-sdl3.dll", "kmrp-sdl3-LICENSE.txt" };

        // Which KPM edition patch each change belongs to; K1KpmApplier.cpp applies a
        // change when its patch is installed (ticked, in KOTOR Patch Manager).
        private const uint FeatureCore = 1, FeatureMovies = 2, FeatureMapNotes = 4;

        private sealed class Section
        {
            internal string Name;
            internal uint Va;
            internal int RawOffset;
            internal int RawSize;
            internal uint Characteristics;
        }

        private sealed class Relocation
        {
            internal uint Kind;
            internal uint Field;
        }

        // ------------------------------------------------------------ state

        internal static string ManifestPath(string executablePath)
        {
            return Path.Combine(Path.GetDirectoryName(Path.GetFullPath(executablePath)), ManifestName);
        }

        private static string FolderOf(string executablePath)
        {
            return Path.GetDirectoryName(Path.GetFullPath(executablePath));
        }

        internal static bool IsInstalled(string executablePath)
        {
            try { return File.Exists(ManifestPath(executablePath)); }
            catch { return false; }
        }

        /// <summary>Steam's swkotor.exe, which only this edition supports.</summary>
        internal static bool IsSteam(string targetPath)
        {
            try
            {
                return File.Exists(targetPath) && new FileInfo(targetPath).Length == SteamLength &&
                    GoldPatch.HashFile(targetPath) == GoldPatch.SteamHash;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>The executable as this edition sees it: CD 1.03 as the standalone
        /// accepts it, or Steam's.</summary>
        private static ExecutableState InspectSource(string targetPath)
        {
            ExecutableState standalone = PatchOperations.InspectStandalone(targetPath);
            return standalone == ExecutableState.Unsupported && IsSteam(targetPath)
                ? ExecutableState.SupportedClean : standalone;
        }

        /// <summary>An install by the standalone installer, which wrote the gold delta
        /// into swkotor.exe, which this replaces. (KMRP for KPM, the separate installer
        /// until 2026-09-29, refused it.)</summary>
        private static bool IsStandaloneInstall(string targetPath)
        {
            return PatchOperations.InspectStandalone(targetPath) == ExecutableState.Gold;
        }

        /// <summary>Gold here means "KMRP is installed": the executable is the unmodified
        /// one either way, bar the large-address flag. An install by the standalone
        /// installer is Gold too: this can restore it or replace it.</summary>
        internal static ExecutableState Inspect(string targetPath)
        {
            ExecutableState source = InspectSource(targetPath);
            if (source != ExecutableState.SupportedClean)
                return source;
            return IsInstalled(targetPath) ? ExecutableState.Gold : ExecutableState.SupportedClean;
        }

        internal static string Describe(string targetPath)
        {
            if (IsStandaloneInstall(targetPath))
                return "An earlier KMRP, which patched swkotor.exe, is installed. Installing replaces it.";
            if (IsInstalled(targetPath))
                return IsInstalledForPatchManager(targetPath)
                    ? "KMRP is installed for KOTOR Patch Manager."
                    : "KMRP is installed.";
            if (IsSteam(targetPath))
                return "Steam's swkotor.exe — ready to install.";
            return PatchOperations.DescribeStandalone(targetPath);
        }

        internal static bool CanRestore(string targetPath)
        {
            if (IsStandaloneInstall(targetPath))
                return PatchOperations.CanRestoreStandalone(targetPath);
            return IsInstalled(targetPath) && InspectSource(targetPath) == ExecutableState.SupportedClean;
        }

        /// <summary>The current install was made for KOTOR Patch Manager: its manifest
        /// records no runtime of its own.</summary>
        internal static bool IsInstalledForPatchManager(string targetPath)
        {
            return IsInstalled(targetPath) && !ReadRecords(targetPath).Exists(r => r[0] == "moved");
        }

        internal static bool TryReadInstalledResolution(string targetPath, out int width, out int height)
        {
            if (IsStandaloneInstall(targetPath))
                return PatchOperations.TryReadInstalledResolutionStandalone(targetPath, out width, out height);
            width = 0;
            height = 0;
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length == 3 && parts[0] == "resolution")
                        return Int32.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out width) &&
                            Int32.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out height);
                }
            }
            catch { }
            return false;
        }

        // ------------------------------------------------------------ install

        internal static void Install(string targetPath, int width, int height, Action<string> report,
            Action<int, string> progress)
        {
            SafeProgress(progress, 0, "Preparing game files…");
            targetPath = Path.GetFullPath(targetPath);
            if (!File.Exists(targetPath))
                throw new FileNotFoundException("swkotor.exe was not found.", targetPath);
            ResolutionChoice resolution = ResolutionCatalog.Find(width, height);

            // Every check that can refuse comes first, so a refusal changes nothing.
            SafeProgress(progress, 5, "Checking game files…");
            bool standalone = IsStandaloneInstall(targetPath);
            if (standalone && !PatchOperations.CanRestoreStandalone(targetPath))
                throw new InvalidOperationException(
                    "An earlier KMRP, which patched swkotor.exe, is installed, and its backup of " +
                    "the original swkotor.exe or swkotor.ini is missing or damaged, so it cannot " +
                    "be removed. Reinstall the game's original swkotor.exe, then install again.");
            bool steam = IsSteam(targetPath);
            if (!standalone && !steam && !GoldPatch.IsSupportedSourceFile(targetPath))
                throw new InvalidDataException("This swkotor.exe is not supported. No changes were made.");
            if (!File.Exists(IniOperations.PathForExecutable(targetPath)))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before installing.",
                    IniOperations.PathForExecutable(targetPath));
            string foreign = ForeignRuntimeFile(targetPath, standalone);
            bool engine = foreign == null && !KmrpSettings.PatchManager;
            if (engine)
                RequireBink(targetPath);
            else if (foreign != null)
                SafeReport(report, foreign + " is in the game folder: KOTOR Patch Manager manages this " +
                    "game, so KMRP is installed for it.");

            if (standalone)
            {
                // The standalone installer's own restore puts back the executable it
                // rewrote, from the backup it made, and everything else it installed
                // -- its runtime, K1DC, Override, the INI -- before this install starts.
                SafeProgress(progress, 6, "Removing the earlier KMRP…");
                SafeReport(report, "An earlier KMRP, which patched swkotor.exe, is installed. " +
                    "Restoring the original game files before installing this one.");
                PatchOperations.RestoreStandalone(targetPath, report, null);
                if (IsStandaloneInstall(targetPath) || !GoldPatch.IsSupportedSourceFile(targetPath))
                    throw new InvalidDataException("The earlier KMRP could not be removed, so nothing of this one was installed.");
            }
            if (IsInstalled(targetPath))
            {
                SafeReport(report, "Replacing the installed KMRP files.");
                Restore(targetPath, report, null);
            }

            // The final image, built as the standalone installer builds it, from the
            // unmodified executable's bytes this installer carries -- the same for CD
            // 1.03 and Steam, whose code is encrypted on disk. Nothing of it is written
            // to swkotor.exe.
            SafeProgress(progress, 10, "Building KMRP's game changes…");
            byte[] clean = OriginalsImage();
            byte[] final = GoldPatch.Load().ApplyToOriginals(clean, resolution, true);
            byte[] data = BuildData(clean, final);

            string folder = FolderOf(targetPath);
            List<string[]> records = new List<string[]>();
            IniEditState iniState = null;
            DpiCompatibilityEditState dpiState = null;
            NvidiaPresentEditState nvidiaState = null;
            OverrideEditState overrideState = null;
            try
            {
                SafeProgress(progress, 15, "Updating display settings…");
                dpiState = DpiCompatibilityOperations.Install(targetPath, report);
                nvidiaState = NvidiaPresentOperations.Install(targetPath, report);
                iniState = IniOperations.Configure(targetPath, width, height, report);
                overrideState = OverrideOperations.Install(targetPath, resolution, report, progress);

                SafeProgress(progress, 94, engine ? "Installing KMRP's patches…" :
                    "Writing KMRP's data for KOTOR Patch Manager…");
                WriteOwned(folder, DataName, data, records);
                for (int i = 0; i < SupportResources.Length; i++)
                    WriteOwned(folder, SupportFiles[i], ReadResource(SupportResources[i]), records);
                // The controller's settings are the player's to edit: written only when
                // absent, and claimed only then, as the standalone installer does.
                string settings = Path.Combine(folder, ControllerOperations.SettingsName);
                if (!File.Exists(settings))
                    WriteOwned(folder, ControllerOperations.SettingsName,
                        new UTF8Encoding(false).GetBytes(ControllerOperations.DefaultSettings), records);
                if (engine)
                {
                    List<string> patches = ChosenPatches();
                    InstallEngine(folder, Path.GetFileName(targetPath), steam, patches, records, report);
                    SafeProgress(progress, 97, "Setting the 4 GB flag…");
                    if (!steam && SetLargeAddressAware(targetPath, patches, records, report))
                        records.Add(new[] { "laa", "set" });
                    if (KmrpSettings.DriverCompatibility)
                        DriverCompatOperations.Install(targetPath, report);
                }
                WriteManifest(targetPath, width, height, records);
            }
            catch
            {
                if (engine)
                {
                    try { DriverCompatOperations.Restore(targetPath, null); }
                    catch { }
                }
                RemoveOwned(folder, records, null);
                UndoEngineChanges(targetPath, records, null);
                try { File.Delete(ManifestPath(targetPath)); }
                catch { }
                OverrideOperations.Rollback(overrideState);
                try { IniOperations.Rollback(iniState); }
                catch { }
                try { DpiCompatibilityOperations.Rollback(dpiState); }
                catch { }
                NvidiaPresentOperations.Rollback(nvidiaState);
                throw;
            }
            SafeProgress(progress, 100, "Installed");
            if (engine)
            {
                SafeReport(report, "KOTOR is ready to play at " +
                    width.ToString(CultureInfo.InvariantCulture) + " × " +
                    height.ToString(CultureInfo.InvariantCulture) + ". Start it as you always do" +
                    (steam ? ", from Steam." : "."));
                if (steam)
                    SafeReport(report, "Steam's swkotor.exe was not modified: Steam refuses to start " +
                        "a changed one, so it runs without the 4 GB flag. If Steam verifies the game's " +
                        "files, it puts its own binkw32.dll back; install KMRP again afterwards.");
                return;
            }
            SafeReport(report, "KMRP is installed for KOTOR Patch Manager at " +
                width.ToString(CultureInfo.InvariantCulture) + " × " +
                height.ToString(CultureInfo.InvariantCulture) + ". swkotor.exe was not modified.");
            SafeReport(report, "Now open KOTOR Patch Manager, add KMRP's four .kpatch files from the " +
                "\"KPM patches\" folder beside this installer to its patch folder, and tick KMRP, plus " +
                "whichever of KMRP Controller, KMRP Movies and KMRP Map Notes you want. KMRP includes " +
                "the 4 GB, texture, grass and save-game memory fixes, so leave KPM's own ones " +
                "unticked. Press Apply, and start the game with Launch.");
            if (steam)
                SafeReport(report, "Steam: in KOTOR Patch Manager choose the proxy deployment, " +
                    "and start the game from Steam. Steam's swkotor.exe cannot take the 4 GB flag.");
        }

        /// <summary>Removes what Install recorded, of either kind: the manifest says
        /// what was installed. An install by the standalone installer is its own
        /// restore's.</summary>
        internal static void Restore(string targetPath, Action<string> report, Action<int, string> progress)
        {
            SafeProgress(progress, 0, "Preparing to restore…");
            targetPath = Path.GetFullPath(targetPath);
            if (!IsInstalled(targetPath) && IsStandaloneInstall(targetPath))
            {
                PatchOperations.RestoreStandalone(targetPath, report, progress);
                return;
            }
            string folder = FolderOf(targetPath);
            List<string[]> records = ReadRecords(targetPath);
            bool engine = records.Exists(r => r[0] == "moved");
            // KOTOR Patch Manager took over the runtime this install put in -- its Apply
            // rewrote patch_config.toml, and it may have re-extracted KMRP's modules byte
            // for byte and kept the proxy -- so the runtime is KPM's now, and removing
            // any of it would break KPM's install. Only KMRP's own content goes.
            bool handedOver = engine && ConfigChangedSinceInstall(folder, records);
            if (handedOver)
            {
                records = records.FindAll(r => !IsRuntimeRecord(r));
                SafeReport(report, "KOTOR Patch Manager has taken over the runtime KMRP installed " +
                    "(its patch_config.toml changed), so the runtime was left in place for it.");
            }
            OverrideOperations.Restore(targetPath, report, progress);
            // K1DC keeps its own manifest, and only an install with KMRP's own runtime
            // installs it; without the manifest this does nothing.
            DriverCompatOperations.Restore(targetPath, report);
            RemoveOwned(folder, records, report);
            UndoEngineChanges(targetPath, records, report);
            DpiCompatibilityOperations.Restore(targetPath, report);
            NvidiaPresentOperations.Restore(targetPath, report);
            SafeProgress(progress, 92, "Restoring display settings…");
            IniOperations.Restore(targetPath, report);
            try { File.Delete(ManifestPath(targetPath)); }
            catch { }
            SafeProgress(progress, 100, "Restore complete");
            SafeReport(report, engine && !handedOver
                ? "The original game files and settings have been restored."
                : "KMRP's files and settings have been removed. " +
                  "Untick KMRP in KOTOR Patch Manager and press Apply to finish.");
        }

        /// <summary>The patch_config.toml this install wrote has been replaced by another
        /// one. Gone altogether is not a takeover: KPM's own "remove all patches" deletes
        /// it with the rest of the runtime, and then nothing runs the game through it,
        /// so the usual restore cleans up what is left, the 4 GB flag included.</summary>
        private static bool ConfigChangedSinceInstall(string folder, List<string[]> records)
        {
            string[] config = records.Find(r => r[0] == "file" &&
                String.Equals(r[1], ConfigName, StringComparison.OrdinalIgnoreCase));
            if (config == null)
                return false;
            string path = Path.Combine(folder, ConfigName);
            return File.Exists(path) && GoldPatch.HashFile(path) != config[2];
        }

        /// <summary>A record of KOTOR Patch Manager's runtime as this install laid it out:
        /// the runtime, its config, its identity file and the backup it restores from,
        /// the modules, the proxy and the rename, and the 4 GB flag KPM's own KMRP patch
        /// sets too.</summary>
        private static bool IsRuntimeRecord(string[] record)
        {
            if (record[0] == "moved" || record[0] == "laa")
                return true;
            if (record[0] != "file")
                return false;
            string name = record[1];
            return String.Equals(name, RuntimeName, StringComparison.OrdinalIgnoreCase) ||
                String.Equals(name, ConfigName, StringComparison.OrdinalIgnoreCase) ||
                String.Equals(name, KpmStateName, StringComparison.OrdinalIgnoreCase) ||
                String.Equals(name, BinkName, StringComparison.OrdinalIgnoreCase) ||
                name.IndexOf(KpmBackupInfix, StringComparison.OrdinalIgnoreCase) > 0 ||
                name.StartsWith(PatchFolder + "\\", StringComparison.OrdinalIgnoreCase);
        }

        // ------------------------------------------------------------ KMRP's own engine

        /// <summary>The first of KOTOR Patch Manager's runtime files in the game folder
        /// that is not KMRP's, or null: then the game is managed by KOTOR Patch Manager
        /// -- KPM's own, most likely -- and KMRP installs for it rather than beside it,
        /// since two runtimes would fight over binkw32.dll and patch_config.toml. A file
        /// is KMRP's when this install's manifest records it and it is still as
        /// recorded (KPM's Apply over KMRP's install replaces them), or when it is the
        /// standalone runtime's patch_config.toml and that install is about to be
        /// restored. Until 2026-09-29 such a folder refused the install.</summary>
        private static string ForeignRuntimeFile(string targetPath, bool standalone)
        {
            string folder = FolderOf(targetPath);
            List<string[]> ours = ReadRecords(targetPath);
            foreach (string name in new[] { BinkMovedName, RuntimeName, ConfigName, KpmStateName })
            {
                string path = Path.Combine(folder, name);
                if (!File.Exists(path))
                    continue;
                string hash = GoldPatch.HashFile(path);
                bool recorded = ours.Exists(r =>
                    (r[0] == "file" && String.Equals(r[1], name, StringComparison.OrdinalIgnoreCase) && r[2] == hash) ||
                    (r[0] == "moved" && String.Equals(r[2], name, StringComparison.OrdinalIgnoreCase) && r[3] == hash));
                if (recorded || (standalone && name == ConfigName &&
                                 ControllerOperations.Owns(targetPath, ConfigName)))
                    continue;
                return name;
            }
            return null;
        }

        /// <summary>KMRP's own runtime loads through the game's binkw32.dll: refuses,
        /// before anything changes, a folder without it -- unless KMRP's own install
        /// moved it aside, which restore puts back.</summary>
        private static void RequireBink(string targetPath)
        {
            string folder = FolderOf(targetPath);
            if (ReadRecords(targetPath).Exists(r => r[0] == "moved") ||
                File.Exists(Path.Combine(folder, BinkName)))
                return;
            throw new FileNotFoundException("binkw32.dll was not found beside swkotor.exe. KMRP loads " +
                "through it; restore the game's own binkw32.dll (in Steam: Properties, Installed " +
                "Files, Verify integrity) and try again.", Path.Combine(folder, BinkName));
        }

        /// <summary>KMRP's patches the options choose, in EnginePatches' order: KMRP and
        /// KMRP Movies always, KMRP Map Notes with the marker fixes, KMRP Controller with
        /// controller support.</summary>
        private static List<string> ChosenPatches()
        {
            List<string> patches = new List<string>();
            foreach (string id in EnginePatches)
            {
                if (id == "kmrp-map-notes" && !KmrpSettings.MarkerFixes)
                    continue;
                if (id == "kmrp-controller" && !KmrpSettings.ControllerSupport)
                    continue;
                patches.Add(id);
            }
            return patches;
        }

        /// <summary>KOTOR Patch Manager's runtime, the proxy that loads it, KMRP's patch
        /// modules and patch_config.toml -- the layout KPM's own proxy deployment gives
        /// a game folder. Every file goes through WriteOwned, which refuses one it did
        /// not write; the game's binkw32.dll is renamed, and recorded, first.</summary>
        private static void InstallEngine(string folder, string exeName, bool steam, List<string> patches,
            List<string[]> records, Action<string> report)
        {
            WriteOwned(folder, RuntimeName, ReadResource("Kmrp.engine.runtime"), records);
            WriteOwned(folder, KpmLicenseName, ReadResource("Kmrp.engine.license"), records);
            // Every patch with detours loads its own copy of the one module, as KPM
            // extracts one per patch: the applier runs in the core's copy only
            // (kmrp.dll), and the core hands its frames to KMRP Controller's copy when
            // that one is loaded (K1NativeJoystick.cpp).
            byte[] module = ReadResource("Kmrp.controller.module");
            StringBuilder config = new StringBuilder();
            config.Append("target_version_sha = \"").Append(steam ? GoldPatch.SteamHash : GoldPatch.SourceHash)
                .Append("\"\n");
            foreach (string id in patches)
            {
                string section = Encoding.UTF8.GetString(ReadResource("Kmrp.engine.config." + id));
                config.Append('\n').Append(section);
                if (section.Contains("dll = \"" + PatchFolder + "/" + id + ".dll\""))
                {
                    Directory.CreateDirectory(Path.Combine(folder, PatchFolder));
                    WriteOwned(folder, PatchFolder + "\\" + id + ".dll", module, records);
                }
            }
            WriteOwned(folder, ConfigName, new UTF8Encoding(false).GetBytes(config.ToString()), records);
            if (!steam)
                WriteOwned(folder, KpmStateName, new UTF8Encoding(false).GetBytes(
                    KpmState(Path.Combine(folder, exeName), patches)), records);

            // The proxy last, since it is what makes the game load the rest.
            string bink = Path.Combine(folder, BinkName);
            string moved = Path.Combine(folder, BinkMovedName);
            string binkHash = GoldPatch.HashFile(bink);
            File.Move(bink, moved);
            records.Add(new[] { "moved", BinkName, BinkMovedName, binkHash });
            WriteOwned(folder, BinkName, ReadResource("Kmrp.engine.proxy"), records);
            SafeReport(report, "Installed KOTOR Patch Manager's runtime with KMRP's patches: " +
                String.Join(", ", patches.ToArray()) + ".");
        }

        /// <summary>kpm_install_state.json, as KOTOR Patch Manager 0.7.1 writes it
        /// (ManagedInstallState, schema 1): the executable was CD 1.03 before a patch
        /// changed it. KPM knows a game by its executable's hash, and the 4 GB flag this
        /// install sets makes CD 1.03's one KPM does not know. KPM's Apply first clears
        /// what is installed -- patch_config.toml, which also names the hash, with it --
        /// and then identifies the game, from this file when the hash is unknown
        /// (GameDetector.DetectVersionFromManagedInstallState). With neither this nor
        /// a backup (WriteKpmBackup), KPM refused every patch over this install on
        /// 2026-09-29, having already removed KMRP's runtime; with this alone, KPM 0.7.1
        /// applied KMRP's patches and another beside them. Where this install set the
        /// flag, the backup lets KPM start from the unmodified file anyway; this is what
        /// identifies an executable that already had the flag, when there is no backup.
        /// Enum values are KPM's (Platform.Windows 0, Distribution.GOG 0,
        /// Architecture.x86 0, GameTitle.KOTOR1 1), as its table has CD 1.03.
        /// Steam's executable is never changed, so KPM knows it by hash and this is
        /// not written there.</summary>
        private static string KpmState(string exePath, List<string> patches)
        {
            string now = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);
            string hash = GoldPatch.SourceHash;
            string size = GoldPatch.SourceLength.ToString(CultureInfo.InvariantCulture);
            StringBuilder ids = new StringBuilder();
            foreach (string id in patches)
                ids.Append(ids.Length > 0 ? ", " : "").Append('"').Append(id).Append('"');
            return "{\r\n" +
                "  \"SchemaVersion\": 1,\r\n" +
                "  \"GameExePath\": \"" + JsonString(Path.GetFullPath(exePath)) + "\",\r\n" +
                "  \"GameExeFileName\": \"" + JsonString(Path.GetFileName(exePath)) + "\",\r\n" +
                "  \"OriginalHash\": \"" + hash + "\",\r\n" +
                "  \"OriginalFileSize\": " + size + ",\r\n" +
                "  \"OriginalVersion\": {\r\n" +
                "    \"Platform\": 0,\r\n    \"Distribution\": 0,\r\n    \"Version\": \"1.0.3\",\r\n" +
                "    \"Architecture\": 0,\r\n    \"Title\": 1,\r\n" +
                "    \"FileSize\": " + size + ",\r\n    \"Hash\": \"" + hash + "\"\r\n  },\r\n" +
                "  \"CurrentHash\": null,\r\n  \"CurrentFileSize\": null,\r\n" +
                "  \"InstalledPatches\": [" + ids + "],\r\n" +
                "  \"LibraryProxyInstalled\": true,\r\n  \"LinkedDependencyInstalled\": false,\r\n" +
                "  \"CreatedAt\": \"" + now + "\",\r\n  \"UpdatedAt\": \"" + now + "\"\r\n" +
                "}\r\n";
        }

        private static string JsonString(string value)
        {
            StringBuilder text = new StringBuilder();
            foreach (char c in value)
            {
                if (c == '\\' || c == '"')
                    text.Append('\\').Append(c);
                else if (c < ' ')
                    text.Append("\\u").Append(((int)c).ToString("X4", CultureInfo.InvariantCulture));
                else
                    text.Append(c);
            }
            return text.ToString();
        }

        /// <summary>Sets IMAGE_FILE_LARGE_ADDRESS_AWARE on CD 1.03's swkotor.exe, the
        /// one-bit change the standalone installer also made (PeCompatibility), and
        /// checks the result is the known large-address file; first it leaves a backup
        /// of the unmodified file for KOTOR Patch Manager (WriteKpmBackup). False when
        /// there was nothing to do: the flag already set, by the player or another tool,
        /// is left alone, and restore leaves it too.</summary>
        private static bool SetLargeAddressAware(string targetPath, List<string> patches, List<string[]> records,
            Action<string> report)
        {
            string hash = GoldPatch.HashFile(targetPath);
            if (hash == PeCompatibility.LargeAddressAwareSourceHash)
            {
                SafeReport(report, "swkotor.exe already has the 4 GB flag.");
                return false;
            }
            if (hash != GoldPatch.SourceHash)
                throw new InvalidDataException("swkotor.exe changed during the install. No changes were kept.");
            WriteKpmBackup(targetPath, patches, records);
            WriteCharacteristics(targetPath, PeCompatibility.LargeAddressAwareCharacteristics);
            if (GoldPatch.HashFile(targetPath) != PeCompatibility.LargeAddressAwareSourceHash)
            {
                WriteCharacteristics(targetPath, PeCompatibility.OriginalCharacteristics);
                throw new IOException("Setting the 4 GB flag on swkotor.exe could not be verified. No changes were kept.");
            }
            SafeReport(report, "Set the 4 GB flag on swkotor.exe (one bit of its header).");
            return true;
        }

        /// <summary>A copy of the unmodified swkotor.exe as KOTOR Patch Manager 0.7.1
        /// backs one up (BackupManager.CreateBackup, BackupInfo): the file, and its
        /// metadata beside it. KPM's Apply begins by restoring the newest backup and
        /// deleting it (PatchRemover.RemoveAllPatches), so over this install it starts
        /// from the unmodified file, knows it by its hash, and sets the 4 GB flag itself
        /// from KMRP.kpatch's static hook, keeping a backup of its own -- the flag is
        /// then KPM's to take back. Without this, KPM backed up the flagged file on
        /// 2026-09-29, and its "uninstall all" -- every patch unticked -- restores the
        /// newest backup and deletes kpm_install_state.json, which would leave a flagged
        /// executable KPM no longer identifies (read in KPM's source). Restore removes
        /// both files while they are as written.</summary>
        private static void WriteKpmBackup(string targetPath, List<string> patches, List<string[]> records)
        {
            string folder = FolderOf(targetPath);
            string name = Path.GetFileName(targetPath) + KpmBackupInfix +
                DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
            WriteOwned(folder, name, File.ReadAllBytes(targetPath), records);
            if (records[records.Count - 1][2] != GoldPatch.SourceHash)
                throw new InvalidDataException("swkotor.exe changed during the install. No changes were kept.");
            StringBuilder ids = new StringBuilder();
            foreach (string id in patches)
                ids.Append(ids.Length > 0 ? ", " : "").Append('"').Append(id).Append('"');
            string json = "{\r\n" +
                "  \"OriginalPath\": \"" + JsonString(targetPath) + "\",\r\n" +
                "  \"BackupPath\": \"" + JsonString(Path.Combine(folder, name)) + "\",\r\n" +
                "  \"Hash\": \"" + GoldPatch.SourceHash + "\",\r\n" +
                "  \"FileSize\": " + GoldPatch.SourceLength.ToString(CultureInfo.InvariantCulture) + ",\r\n" +
                "  \"CreatedAt\": \"" + DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture) + "\",\r\n" +
                "  \"DetectedVersion\": null,\r\n" +
                "  \"InstalledPatches\": [" + ids + "]\r\n" +
                "}\r\n";
            WriteOwned(folder, name + ".json", new UTF8Encoding(false).GetBytes(json), records);
        }

        private static void WriteCharacteristics(string targetPath, ushort value)
        {
            try
            {
                FileAttributes attributes = File.GetAttributes(targetPath);
                if ((attributes & FileAttributes.ReadOnly) != 0)
                    File.SetAttributes(targetPath, attributes & ~FileAttributes.ReadOnly);
                using (FileStream stream = new FileStream(targetPath, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
                {
                    stream.Position = PeCompatibility.CharacteristicsOffset;
                    stream.WriteByte((byte)(value & 0xFF));
                    stream.WriteByte((byte)(value >> 8));
                    stream.Flush(true);
                }
            }
            catch (IOException error)
            {
                throw new IOException(InUseMessage(targetPath), error);
            }
            catch (UnauthorizedAccessException error)
            {
                throw new IOException(InUseMessage(targetPath), error);
            }
        }

        private static string InUseMessage(string path)
        {
            return Path.GetFileName(path) + " is being used by another program, so it could not be " +
                "updated. Close KOTOR, Steam, and any editor with the file open, then try again.";
        }

        /// <summary>Puts back what InstallEngine and SetLargeAddressAware changed, after
        /// RemoveOwned has removed the files: the game's binkw32.dll, and the
        /// large-address flag this install set. A file changed since is left, and
        /// said so.</summary>
        private static void UndoEngineChanges(string targetPath, List<string[]> records, Action<string> report)
        {
            string folder = FolderOf(targetPath);
            foreach (string[] record in records)
            {
                if (record[0] != "moved" || record.Length != 4)
                    continue;
                string original = Path.Combine(folder, record[1]);
                string moved = Path.Combine(folder, record[2]);
                if (!File.Exists(moved))
                    continue;
                if (GoldPatch.HashFile(moved) != record[3])
                {
                    SafeReport(report, "Left " + record[2] + " in place because it changed after install.");
                    continue;
                }
                if (!File.Exists(original))
                    File.Move(moved, original);
                else if (GoldPatch.HashFile(original) == record[3])
                    // The original is back already -- Steam's file check restores it --
                    // so the renamed copy is a duplicate.
                    File.Delete(moved);
                else
                    SafeReport(report, "Left " + record[2] + " in place: " + record[1] +
                        " changed after install, so the game's own copy was not put back.");
            }
            string patches = Path.Combine(folder, PatchFolder);
            try
            {
                if (Directory.Exists(patches) && Directory.GetFileSystemEntries(patches).Length == 0)
                    Directory.Delete(patches);
            }
            catch { }
            if (records.Exists(r => r[0] == "laa" && r.Length == 2 && r[1] == "set"))
            {
                if (File.Exists(targetPath) &&
                    GoldPatch.HashFile(targetPath) == PeCompatibility.LargeAddressAwareSourceHash)
                {
                    WriteCharacteristics(targetPath, PeCompatibility.OriginalCharacteristics);
                    if (GoldPatch.HashFile(targetPath) != GoldPatch.SourceHash)
                        throw new IOException("Clearing the 4 GB flag on swkotor.exe could not be verified.");
                }
                else
                    SafeReport(report, "Left swkotor.exe's header alone because it changed after install.");
            }
        }

        // ------------------------------------------------------------ the data file

        /// <summary>kmrp-kpm.dat: how <paramref name="final"/> differs from
        /// <paramref name="clean"/>, for K1KpmApplier.cpp, whose header describes the
        /// format. <paramref name="final"/> is built with the map notes enabled; the
        /// data file carries them as KMRP Map Notes' edit. Public to the assembly so a
        /// test can build one without installing.</summary>
        internal static byte[] BuildData(byte[] clean, byte[] final)
        {
            List<Section> original = Sections(clean);
            List<Section> patched = Sections(final);
            List<Relocation> relocations = LoadRelocations();

            // The block: gold's eleven appended sections, 4 KB each, from BlockVa.
            List<Section> block = patched.FindAll(s => s.Va >= BlockVa);
            if (block.Count != BlockSections)
                throw new InvalidDataException("The patched image does not carry KMRP's " +
                    BlockSections + " code sections.");
            for (int i = 0; i < block.Count; i++)
                if (block[i].Va != BlockVa + (uint)(i * 0x1000) || block[i].RawSize != 0x1000)
                    throw new InvalidDataException("KMRP's code sections are not where this build expects them.");
            byte[] blockBytes = new byte[BlockSize];
            Buffer.BlockCopy(final, block[0].RawOffset, blockBytes, 0, BlockSize);

            // KMRP Map Notes: the .kmn enable flag, cleared in the block and set again by
            // the edit when that patch is installed.
            int flag = checked((int)ResolutionPatch.MapNoteFlagOffset) - block[0].RawOffset;
            if (flag < 0 || flag + 4 > BlockSize || BitConverter.ToInt32(blockBytes, flag) == 0)
                throw new InvalidDataException("The map-note flag is not set in KMRP's code sections.");
            byte[] mapNotes = new byte[4];
            Buffer.BlockCopy(blockBytes, flag, mapNotes, 0, 4);
            Array.Clear(blockBytes, flag, 4);
            uint flagVa = BlockVa + (uint)flag;
            foreach (Relocation r in relocations)
                if (r.Field < flagVa + 4 && r.Field + 4 > flagVa)
                    throw new InvalidDataException("A relocation overlaps the map-note flag.");

            // KMRP Movies: the four movie display-mode operands, and every run that
            // enters the movie aspect fit's section.
            Section kmv = block.Find(s => s.Name == ".kmv");
            if (kmv == null)
                throw new InvalidDataException("KMRP's movie section (.kmv) is missing.");
            List<uint> movieOperands = new List<uint>();
            foreach (long offset in ResolutionPatch.MovieWidthOffsets)
                movieOperands.Add(VaOf(original, offset));
            foreach (long offset in ResolutionPatch.MovieHeightOffsets)
                movieOperands.Add(VaOf(original, offset));

            // Which bytes of the original image change, plus every IN field whole, so the
            // module can add its delta to a field inside one run.
            Dictionary<uint, bool> inField = new Dictionary<uint, bool>();
            foreach (Relocation r in relocations)
                if (r.Kind == KindIn)
                    for (uint b = 0; b < 4; b++)
                        inField[r.Field + b] = true;

            List<KeyValuePair<uint, int>> runs = new List<KeyValuePair<uint, int>>();
            foreach (Section s in original)
            {
                int start = -1;
                for (int i = 0; i <= s.RawSize; i++)
                {
                    bool changed = i < s.RawSize &&
                        (clean[s.RawOffset + i] != final[s.RawOffset + i] || inField.ContainsKey(s.Va + (uint)i));
                    if (changed && start < 0)
                        start = i;
                    else if (!changed && start >= 0)
                    {
                        runs.Add(new KeyValuePair<uint, int>(s.Va + (uint)start, i - start));
                        start = -1;
                    }
                }
            }
            foreach (Relocation r in relocations)
            {
                if (r.Kind == KindIn && !runs.Exists(run => r.Field >= run.Key && r.Field + 4 <= run.Key + run.Value))
                    throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                        "Relocation {0:X8} is not inside a changed run.", r.Field));
                if ((r.Kind == KindOut || r.Kind == KindAbs) &&
                    (r.Field < BlockVa || r.Field + 4 > BlockVa + BlockSize))
                    throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                        "Relocation {0:X8} is not inside KMRP's code sections.", r.Field));
            }

            // Each run belongs to one patch, and a Movies run holds nothing else: an
            // operand run lies within its operand, and an entry run leads only into .kmv.
            List<uint> features = new List<uint>();
            foreach (KeyValuePair<uint, int> run in runs)
            {
                uint start = run.Key, end = run.Key + (uint)run.Value;
                uint feature = FeatureCore;
                foreach (uint operand in movieOperands)
                    if (start < operand + 4 && end > operand)
                    {
                        if (start < operand || end > operand + 4)
                            throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                                "The run at {0:X8} holds more than the movie operand at {1:X8}.", start, operand));
                        feature = FeatureMovies;
                    }
                bool intoMovies = false, elsewhere = false;
                foreach (Relocation r in relocations)
                {
                    if (r.Kind != KindIn || r.Field < start || r.Field + 4 > end)
                        continue;
                    int offset = OffsetOf(original, r.Field);
                    uint value = BitConverter.ToUInt32(final, offset);
                    uint relative = unchecked(r.Field + 4 + value);
                    uint target = relative >= BlockVa && relative < BlockVa + BlockSize ? relative : value;
                    if (target >= kmv.Va && target < kmv.Va + (uint)kmv.RawSize)
                        intoMovies = true;
                    else
                        elsewhere = true;
                }
                if (intoMovies)
                {
                    if (elsewhere || feature == FeatureMovies)
                        throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                            "The run at {0:X8} enters the movie section and does something else too.", start));
                    feature = FeatureMovies;
                }
                features.Add(feature);
            }

            using (MemoryStream stream = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(stream))
            {
                writer.Write(Encoding.ASCII.GetBytes("KMRPKPM2"));
                writer.Write(2u);
                writer.Write(BlockVa);
                writer.Write((uint)BlockSize);
                writer.Write((uint)BlockSections);
                foreach (Section s in block)
                    // IMAGE_SCN_MEM_WRITE: .kfs keeps a cache in its own page.
                    writer.Write((s.Characteristics & 0x80000000u) != 0 ? 0x40u : 0x20u);
                writer.Write(blockBytes);
                writer.Write((uint)runs.Count);
                for (int i = 0; i < runs.Count; i++)
                {
                    int offset = OffsetOf(original, runs[i].Key);
                    writer.Write(features[i]);
                    writer.Write(runs[i].Key);
                    writer.Write((uint)runs[i].Value);
                    writer.Write(clean, offset, runs[i].Value);
                    writer.Write(final, offset, runs[i].Value);
                }
                writer.Write(1u);
                writer.Write(FeatureMapNotes);
                writer.Write((uint)flag);
                writer.Write((uint)mapNotes.Length);
                writer.Write(mapNotes);
                writer.Write((uint)relocations.Count);
                foreach (Relocation r in relocations)
                {
                    writer.Write(r.Kind);
                    writer.Write(r.Field);
                }
                writer.Flush();
                byte[] body = stream.ToArray();
                uint hash = 2166136261u;
                foreach (byte b in body)
                {
                    hash ^= b;
                    hash *= 16777619u;
                }
                byte[] result = new byte[body.Length + 4];
                Buffer.BlockCopy(body, 0, result, 0, body.Length);
                Buffer.BlockCopy(BitConverter.GetBytes(hash), 0, result, body.Length, 4);
                return result;
            }
        }

        private static List<Section> Sections(byte[] image)
        {
            int pe = BitConverter.ToInt32(image, 0x3C);
            int count = BitConverter.ToUInt16(image, pe + 6);
            int optional = BitConverter.ToUInt16(image, pe + 20);
            uint imageBase = BitConverter.ToUInt32(image, pe + 24 + 28);
            List<Section> sections = new List<Section>();
            for (int i = 0; i < count; i++)
            {
                int o = pe + 24 + optional + 40 * i;
                sections.Add(new Section
                {
                    Name = Encoding.ASCII.GetString(image, o, 8).TrimEnd('\0'),
                    Va = imageBase + BitConverter.ToUInt32(image, o + 12),
                    RawSize = BitConverter.ToInt32(image, o + 16),
                    RawOffset = BitConverter.ToInt32(image, o + 20),
                    Characteristics = BitConverter.ToUInt32(image, o + 36),
                });
            }
            return sections;
        }

        private static uint VaOf(List<Section> sections, long fileOffset)
        {
            foreach (Section s in sections)
                if (fileOffset >= s.RawOffset && fileOffset < s.RawOffset + (long)s.RawSize)
                    return s.Va + (uint)(fileOffset - s.RawOffset);
            throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                "File offset {0:X} is not in the executable's raw data.", fileOffset));
        }

        private static int OffsetOf(List<Section> sections, uint va)
        {
            foreach (Section s in sections)
                if (va >= s.Va && va < s.Va + (uint)s.RawSize)
                    return s.RawOffset + (int)(va - s.Va);
            throw new InvalidDataException(String.Format(CultureInfo.InvariantCulture,
                "{0:X8} is not in the executable's raw data.", va));
        }

        private static List<Relocation> LoadRelocations()
        {
            string text = Encoding.ASCII.GetString(ReadResource(RelocationResource));
            List<Relocation> relocations = new List<Relocation>();
            bool goldMatches = false;
            foreach (string raw in text.Split('\n'))
            {
                string line = raw.Trim();
                if (line.Length == 0)
                    continue;
                if (line.StartsWith("#", StringComparison.Ordinal))
                {
                    if (line.IndexOf(GoldPatch.TargetHash, StringComparison.OrdinalIgnoreCase) >= 0)
                        goldMatches = true;
                    continue;
                }
                string[] parts = line.Split(' ');
                uint kind = parts[0] == "IN" ? KindIn : parts[0] == "OUT" ? KindOut : parts[0] == "ABS" ? KindAbs : 0;
                uint field;
                if (parts.Length != 2 || kind == 0 ||
                    !UInt32.TryParse(parts[1], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out field))
                    throw new InvalidDataException("The embedded relocation table is damaged: " + line);
                relocations.Add(new Relocation { Kind = kind, Field = field });
            }
            // Computed from a different gold would move the wrong bytes.
            if (!goldMatches)
                throw new InvalidDataException("The embedded relocation table was computed from a different gold build.");
            return relocations;
        }

        /// <summary>Build-time: every field ResolutionPatch reads or writes, at every
        /// resolution in the catalog, as "FILE offset size" lines, for tools/kpm_originals.py. The
        /// installer needs the unmodified executable's bytes under each whole field --
        /// gold changed only some bytes of some fields, and none of a few (the powers
        /// row height stays vanilla's 40 in gold) -- and this list is ResolutionPatch's
        /// own, so it cannot drift from the fields it writes.</summary>
        internal static void WriteResolutionSites(string cleanExe, string outPath)
        {
            byte[] source = File.ReadAllBytes(cleanExe);
            GoldPatch gold = GoldPatch.Load();
            SortedDictionary<long, int> sites = new SortedDictionary<long, int>();
            ResolutionPatch.Touched = new List<long[]>();
            try
            {
                foreach (ResolutionChoice resolution in ResolutionCatalog.Load())
                    gold.Apply(source, resolution, true);
                foreach (long[] touched in ResolutionPatch.Touched)
                {
                    int size;
                    if (!sites.TryGetValue(touched[0], out size) || size < touched[1])
                        sites[touched[0]] = (int)touched[1];
                }
            }
            finally
            {
                ResolutionPatch.Touched = null;
            }
            StringBuilder text = new StringBuilder("# ResolutionPatch's fields, FILE offset and size, from all " +
                ResolutionCatalog.Load().Count.ToString(CultureInfo.InvariantCulture) + " resolutions\r\n");
            foreach (KeyValuePair<long, int> site in sites)
                text.Append(site.Key.ToString("X", CultureInfo.InvariantCulture)).Append(' ')
                    .Append(site.Value.ToString(CultureInfo.InvariantCulture)).Append("\r\n");
            File.WriteAllText(outPath, text.ToString(), new UTF8Encoding(false));
        }

        /// <summary>A picture of CD 1.03 as long as the file: its bytes where
        /// tools/kpm_originals.py carried them (the header, under gold's chunks, the
        /// relocated fields), zero elsewhere. Enough for BuildData, which records only
        /// where gold differs from the unmodified executable.</summary>
        internal static byte[] OriginalsImage()
        {
            byte[] resource = ReadResource(OriginalsResource);
            if (resource.Length < 48 || Encoding.ASCII.GetString(resource, 0, 8) != "KMRPORG1")
                throw new InvalidDataException("The embedded unmodified-executable bytes are damaged.");
            uint hash = 2166136261u;
            for (int i = 0; i < resource.Length - 4; i++)
            {
                hash ^= resource[i];
                hash *= 16777619u;
            }
            if (hash != BitConverter.ToUInt32(resource, resource.Length - 4))
                throw new InvalidDataException("The embedded unmodified-executable bytes are damaged (checksum).");
            StringBuilder source = new StringBuilder();
            for (int i = 8; i < 40; i++)
                source.Append(resource[i].ToString("X2", CultureInfo.InvariantCulture));
            if (source.ToString() != GoldPatch.SourceHash)
                throw new InvalidDataException("The embedded unmodified-executable bytes are from a different executable.");

            byte[] image = new byte[GoldPatch.SourceLength];
            int count = BitConverter.ToInt32(resource, 40);
            int at = 44;
            for (int i = 0; i < count; i++)
            {
                int offset = BitConverter.ToInt32(resource, at);
                int length = BitConverter.ToInt32(resource, at + 4);
                at += 8;
                if (offset < 0 || length <= 0 || offset + (long)length > image.Length ||
                    at + (long)length > resource.Length - 4)
                    throw new InvalidDataException("The embedded unmodified-executable bytes are damaged (range).");
                Buffer.BlockCopy(resource, at, image, offset, length);
                at += length;
            }
            if (at != resource.Length - 4)
                throw new InvalidDataException("The embedded unmodified-executable bytes are damaged (length).");
            return image;
        }

        private static byte[] ReadResource(string name)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
            {
                if (stream == null)
                    throw new InvalidDataException("This build does not carry " + name + ".");
                using (MemoryStream copy = new MemoryStream())
                {
                    stream.CopyTo(copy);
                    return copy.ToArray();
                }
            }
        }

        // ------------------------------------------------------------ owned files

        // The manifest's rows, each a tab-separated record kept as-is in memory:
        //   file   <name> <SHA-256>          a file this install wrote; name may be
        //                                    under patches\
        //   moved  <from> <to> <SHA-256>     a game file renamed (binkw32.dll)
        //   laa    set                       this install set the 4 GB flag
        // KMRP for KPM builds before 2026-09-29 wrote file rows only, the same way.

        private static void WriteOwned(string folder, string name, byte[] data, List<string[]> records)
        {
            string target = Path.Combine(folder, name);
            if (File.Exists(target))
            {
                // Never clobber a file this installer did not write.
                bool ours = false;
                foreach (string[] record in records)
                    if (record[0] == "file" && String.Equals(record[1], name, StringComparison.OrdinalIgnoreCase))
                        ours = true;
                if (!ours)
                    throw new IOException("Left the existing " + name + " alone; " +
                        "KMRP was not installed. Move it aside and try again.");
            }
            File.WriteAllBytes(target, data);
            records.Add(new[] { "file", name, GoldPatch.HashFile(target) });
        }

        private static bool IsOwnedName(string name)
        {
            if (String.IsNullOrEmpty(name) || name.IndexOf('/') >= 0 || name.IndexOf(':') >= 0)
                return false;
            string[] parts = name.Split('\\');
            if (parts.Length == 2 && parts[0] != PatchFolder)
                return false;
            if (parts.Length > 2)
                return false;
            string leaf = parts[parts.Length - 1];
            return leaf.Length > 0 && leaf != "." && leaf != ".." && leaf.IndexOfAny(Path.GetInvalidFileNameChars()) < 0;
        }

        private static void RemoveOwned(string folder, List<string[]> records, Action<string> report)
        {
            int kept = 0;
            foreach (string[] record in records)
            {
                if (record[0] != "file")
                    continue;
                string target = Path.Combine(folder, record[1]);
                if (!File.Exists(target))
                    continue;
                if (GoldPatch.HashFile(target) != record[2])
                {
                    kept++;
                    continue;
                }
                File.Delete(target);
            }
            if (kept > 0)
                SafeReport(report, "Left " + kept.ToString(CultureInfo.InvariantCulture) +
                    " file(s) in place because they changed after install.");
        }

        private static void WriteManifest(string targetPath, int width, int height, List<string[]> records)
        {
            StringBuilder text = new StringBuilder();
            text.Append("version\t").Append(GoldPatch.PatchVersion).Append("\r\n");
            text.Append("resolution\t").Append(width.ToString(CultureInfo.InvariantCulture)).Append('\t')
                .Append(height.ToString(CultureInfo.InvariantCulture)).Append("\r\n");
            foreach (string[] record in records)
                text.Append(String.Join("\t", record)).Append("\r\n");
            File.WriteAllText(ManifestPath(targetPath), text.ToString(), new UTF8Encoding(false));
        }

        private static List<string[]> ReadRecords(string targetPath)
        {
            List<string[]> records = new List<string[]>();
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    // A restore acts on these names, so only what Install writes is
                    // accepted: a file in the game folder or its patches\ folder, and
                    // the one rename.
                    if ((parts.Length == 3 && parts[0] == "file" && IsOwnedName(parts[1])) ||
                        (parts.Length == 4 && parts[0] == "moved" && parts[1] == BinkName && parts[2] == BinkMovedName) ||
                        (parts.Length == 2 && parts[0] == "laa"))
                        records.Add(parts);
                }
            }
            catch { }
            return records;
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report != null)
                report(message);
        }

        private static void SafeProgress(Action<int, string> progress, int value, string message)
        {
            if (progress != null)
                progress(value, message);
        }
    }
}
