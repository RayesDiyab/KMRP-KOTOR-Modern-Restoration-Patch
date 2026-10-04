using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;
using System.Text.RegularExpressions;

namespace Kmrp
{
    /// <summary>KMRP's install, on KOTOR Patch Manager's runtime.
    ///
    /// KMRP's installer does not rewrite swkotor.exe: the executable changes are
    /// KMRP's one KPM patch, "kmrp" (tools/build_native_kpatch.py), whose module
    /// applies them in memory when the game starts
    /// (src/controller-native/K1KpmApplier.cpp, K1RuntimeEngine.cpp) from the recipe
    /// it carries, for the size the game runs at -- the Map Notes part only when that
    /// option is on. Until 2026-10-04 there were four patches and the installer wrote
    /// the recipe for one chosen resolution beside the game as kmrp-kpm.dat, with
    /// that resolution's files in Override. That is what lets one installer serve the
    /// editable CD 1.03 swkotor.exe, GOG's (the same file without a 16-byte watermark,
    /// GameExecutable) and Steam's, whose DRM refuses a changed file. It installs one
    /// of two ways, chosen per install (ManagedByPatchManager):
    ///
    ///   On its own, it installs KOTOR Patch Manager's runtime itself, as KPM's
    ///   proxy deployment lays out a game folder (src/kpm-runtime/README.md): the
    ///   proxy as binkw32.dll, the game's own renamed binkw32Hooked.dll,
    ///   KotorPatcher.dll, patch_config.toml and the module in patches\. The player
    ///   then starts the game as always, from Steam or from swkotor.exe. On CD 1.03
    ///   and GOG's it also sets the large-address flag, the one bit of swkotor.exe it changes,
    ///   leaving KPM a backup of the unmodified file (WriteKpmBackup).
    ///
    ///   For KOTOR Patch Manager -- when KPM's runtime is already in the game folder
    ///   (until 2026-09-30 also when the player chose it in Advanced Settings) -- it
    ///   installs everything but the patch, and the player ticks KMRP's .kpatch
    ///   file in KPM. Until
    ///   2026-09-29 this was a separate installer, KMRP for KPM, compiled from this
    ///   source with KPM_EDITION.
    ///
    /// Either way it replaces an install by the standalone installer, which until
    /// 2026-09-29 wrote the gold delta into swkotor.exe
    /// (PatchOperations.RestoreStandalone), and its own earlier install, of either
    /// kind.
    ///
    /// The module's recipe is built from source (tools/build_windows_engine.py,
    /// tools/build_native_engine.py). Source-authored original-byte guards are carried
    /// with each write, including whole relocated operands. Steam's encrypted
    /// executable is never a build input: the module checks its decrypted
    /// instructions at launch.
    ///
    /// Everything else is shared with the standalone installer's code:
    /// swkotor.ini, DPI and NVIDIA settings, and on its own K1 Modern Driver
    /// Compatibility (DriverCompatOperations). For KOTOR Patch Manager it leaves K1DC
    /// to KPM, where Synchro's K1DC is a .kpatch of its own.</summary>
    internal static class KpmEditionOperations
    {
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
        // KMRP's patch as a .kpatch file for KOTOR Patch Manager's app, embedded
        // (Kmrp.kpatch, tools/build_native_kpatch.py) so that the installer is one file:
        // file name and patch id. With it, the README that explains it
        // (Kmrp.kpatch.readme) and KPM's licence (Kmrp.engine.license). The patch is one
        // since 2026-10-04: the module carries every resolution's files, the controller
        // and SDL, and controller support and map notes are its options.
        // Until then there were four, KMRP with KMRP Controller, KMRP Movies and KMRP Map
        // Notes beside it; their names are still accepted in an older install's records
        // (IsKpatchPath), so that restore can remove them.
        private const string PatchId = "kmrp";
        private const string KpatchResource = "Kmrp.kpatch";
        private const string KpatchModuleEntry = "binaries/windows_x86.dll";
        private static readonly string[,] Kpatches =
        {
            { "KMRP.kpatch", PatchId },
        };
        private static readonly string[] RetiredKpatchNames =
            { "KMRP Controller.kpatch", "KMRP Movies.kpatch", "KMRP Map Notes.kpatch" };
        private const string KpatchFolderName = "KPM patches";
        private const string KpatchReadmeName = "README.txt";
        private const string KpatchLicenseName = "LICENSE-KOTOR-PATCH-MANAGER.txt";
        // Every patch id KMRP has installed: "kmrp" now, and the three beside it that
        // an install made before 2026-10-04 has. Restore recognises an install that
        // KOTOR Patch Manager took over by these (KpmHoldsOnlyKmrp, RemoveKpmRuntime).
        private static readonly string[] EnginePatches =
            { "kmrp", "kmrp-movies", "kmrp-map-notes", "kmrp-controller" };
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
            return GameExecutable.Identify(targetPath) == GameExecutable.Steam;
        }

        /// <summary>The executable as this edition sees it: CD 1.03 or GOG's as the
        /// standalone accepts them, or Steam's.</summary>
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
            if (!standalone && GameExecutable.Identify(targetPath) == null)
                throw new InvalidDataException("This swkotor.exe is not the Steam, GOG or Editable 1.03 " +
                    "version KMRP supports. No changes were made.");
            if (!File.Exists(IniOperations.PathForExecutable(targetPath)))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before installing.",
                    IniOperations.PathForExecutable(targetPath));
            string foreign = ForeignRuntimeFile(targetPath, standalone);
            // KPM's own files decide, since 2026-09-30 alone: the Advanced Settings
            // option that also chose an install for KPM was removed (MainForm).
            bool engine = foreign == null;
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
                // Installing for KPM: a runtime KPM took over stays KPM's, even with
                // only KMRP's patches in it, since this install puts nothing in its place.
                Restore(targetPath, report, null, !engine);
            }
            // After the restores above, which leave it unmodified or with a 4 GB flag
            // that was there before KMRP.
            GameExecutable exe = GameExecutable.Identify(targetPath);
            if (exe == null)
                throw new InvalidDataException("swkotor.exe is not a version KMRP supports after the earlier " +
                    "install was removed, so nothing of this one was installed.");
            bool steam = exe.IsSteam;
            SafeReport(report, "Game version: " + exe.Name + ".");

            // Nothing is built for the resolution: the patch's module carries the engine
            // changes and every resolution's files, and applies the size the game is
            // running at. The size given here is only where swkotor.ini starts the game.
            string folder = FolderOf(targetPath);
            List<string[]> records = new List<string[]>();
            IniEditState iniState = null;
            DpiCompatibilityEditState dpiState = null;
            NvidiaPresentEditState nvidiaState = null;
            string kpatchFolder = null;
            try
            {
                SafeProgress(progress, 15, "Updating display settings…");
                dpiState = DpiCompatibilityOperations.Install(targetPath, report);
                nvidiaState = NvidiaPresentOperations.Install(targetPath, report);
                iniState = IniOperations.Configure(targetPath, width, height, report);

                SafeProgress(progress, 30, engine ? "Installing KMRP's patch…" :
                    "Preparing KMRP's patch for KOTOR Patch Manager…");
                // The controller's settings are the player's to edit: written only when
                // absent, and claimed only then, as the standalone installer does.
                string settings = Path.Combine(folder, ControllerOperations.SettingsName);
                if (!File.Exists(settings))
                    WriteOwned(folder, ControllerOperations.SettingsName,
                        new UTF8Encoding(false).GetBytes(ControllerOperations.DefaultSettings), records);
                // The resolutions the game is to offer, when the player chose them: read
                // by the patch's module whoever installs the patch (ResolutionSelection).
                string chosenSizes = ResolutionSelection.FileText();
                if (chosenSizes != null)
                    WriteOwned(folder, ResolutionSelection.FileName, new UTF8Encoding(false).GetBytes(chosenSizes), records);
                if (engine)
                {
                    List<string> patches = ChosenPatches();
                    InstallEngine(folder, Path.GetFileName(targetPath), exe, patches, records, report);
                    SafeProgress(progress, 80, "Setting the 4 GB flag…");
                    if (!steam && SetLargeAddressAware(targetPath, exe, patches, records, report))
                        records.Add(new[] { "laa", "set" });
                    if (KmrpSettings.DriverCompatibility)
                        DriverCompatOperations.Install(targetPath, report);
                }
                SafeProgress(progress, 85, "Adding KMRP's patch for KOTOR Patch Manager…");
                kpatchFolder = DeliverKpatches(folder, !engine, records, report);
                WriteManifest(targetPath, width, height, records);
            }
            catch
            {
                if (engine)
                {
                    try { DriverCompatOperations.Restore(targetPath, null); }
                    catch { }
                }
                RemoveKpatches(records, null);
                RemoveOwned(folder, records, null);
                RemovePatchOptions(folder, records);
                UndoEngineChanges(targetPath, records, null);
                try { File.Delete(ManifestPath(targetPath)); }
                catch { }
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
                SafeReport(report, "KOTOR is ready to play. It starts at " +
                    width.ToString(CultureInfo.InvariantCulture) + " × " +
                    height.ToString(CultureInfo.InvariantCulture) + "; any other resolution your " +
                    "display offers can be chosen in the game, under Options, Graphics. Start it as " +
                    "you always do" + (steam ? ", from Steam." : "."));
                if (steam)
                    SafeReport(report, "Steam's swkotor.exe was not modified: Steam refuses to start " +
                        "a changed one, so it runs without the 4 GB flag. If Steam verifies the game's " +
                        "files, it puts its own binkw32.dll back; install KMRP again afterwards.");
                if (kpatchFolder != null)
                    SafeReport(report, "KMRP's patch is also in KOTOR Patch Manager's patch " +
                        "folder (" + kpatchFolder + "), so KPM lists it if you add other patches there.");
                return;
            }
            SafeReport(report, "KMRP is prepared for KOTOR Patch Manager. swkotor.exe was not modified.");
            bool inGameFolder = String.Equals(kpatchFolder, Path.Combine(folder, KpatchFolderName),
                StringComparison.OrdinalIgnoreCase);
            SafeReport(report, (inGameFolder
                ? "KMRP's patch, KMRP.kpatch, is in " + kpatchFolder + ". Copy it into KOTOR Patch " +
                  "Manager's patch folder (or choose this folder in KPM), then open KPM"
                : "KMRP's patch, KMRP.kpatch, is in KOTOR Patch Manager's patch folder (" + kpatchFolder +
                  "). Now open KPM") +
                " and tick KMRP. It includes controller support, map notes, the movie fixes and " +
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
            Restore(targetPath, report, progress, false);
        }

        private static void Restore(string targetPath, Action<string> report, Action<int, string> progress,
            bool keepKpmRuntime)
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
            // rewrote some of it, and it may have re-extracted KMRP's modules byte for
            // byte and kept the proxy -- so the runtime is KPM's now, and removing any of
            // it would break KPM's install. Only KMRP's own content goes. Unless KMRP's
            // patches are all KPM has: unticking them in KPM and pressing Apply would
            // remove KPM's whole runtime (PatchRemover.RemoveAllPatches), so that is done
            // here instead, as KPM does it, and the player has nothing left to do in KPM
            // (as the Mac's uninstall does since 2026-10-01, kmrp-mac.sh).
            bool handedOver = engine && RuntimeChangedSinceInstall(folder, records);
            string untouched = null;
            bool whole = handedOver && !keepKpmRuntime && KpmHoldsOnlyKmrp(targetPath, out untouched);
            if (whole)
            {
                // The executable is put back from KPM's backup or its flag cleared by
                // RemoveKpmRuntime, not by this install's record of the flag.
                records = records.FindAll(r => r[0] != "laa");
                SafeReport(report, "KOTOR Patch Manager had taken over KMRP's install, with no other " +
                    "patch, so its runtime is removed as KPM would remove it.");
            }
            else if (handedOver)
            {
                records = records.FindAll(r => !IsRuntimeRecord(r));
                SafeReport(report, "KOTOR Patch Manager has taken over the runtime KMRP installed " +
                    "(its Apply rewrote it), so the runtime was left in place for it.");
            }
            OverrideOperations.Restore(targetPath, report, progress);
            // K1DC keeps its own manifest, and only an install with KMRP's own runtime
            // installs it; without the manifest this does nothing.
            DriverCompatOperations.Restore(targetPath, report);
            RemoveKpatches(records, report);
            if (whole)
                RemoveKpmRuntime(targetPath, untouched, records, report);
            RemoveOwned(folder, records, report);
            RemovePatchOptions(folder, records);
            UndoEngineChanges(targetPath, records, report);
            DpiCompatibilityOperations.Restore(targetPath, report);
            NvidiaPresentOperations.Restore(targetPath, report);
            SafeProgress(progress, 92, "Restoring display settings…");
            IniOperations.Restore(targetPath, report);
            try { File.Delete(ManifestPath(targetPath)); }
            catch { }
            SafeProgress(progress, 100, "Restore complete");
            SafeReport(report, engine && (!handedOver || whole)
                ? "The original game files and settings have been restored."
                : "KMRP's files and settings have been removed. " +
                  "Untick KMRP in KOTOR Patch Manager and press Apply to finish.");
        }

        /// <summary>A file of the runtime this install wrote (IsRuntimeRecord) has been
        /// replaced by another one. Any of them, not patch_config.toml alone: on the Mac
        /// KPM 0.7.1's Apply wrote the config byte for byte as KMRP had, and only the
        /// runtime, the executable and kpm_install_state.json showed the takeover
        /// (2026-10-01); Windows' Apply has not been measured file by file. Gone
        /// altogether is not a takeover: KPM's own "remove all patches" deletes the
        /// runtime, and then nothing runs the game through it, so the usual restore
        /// cleans up what is left, the 4 GB flag included. Nor is the game's own
        /// binkw32.dll back over the proxy, which that removal also does
        /// (KProxyInstaller.Uninstall).</summary>
        private static bool RuntimeChangedSinceInstall(string folder, List<string[]> records)
        {
            string[] rename = records.Find(r => r[0] == "moved" && r.Length == 4);
            foreach (string[] record in records)
            {
                if (record[0] != "file" || !IsRuntimeRecord(record))
                    continue;
                string path = Path.Combine(folder, record[1]);
                if (!File.Exists(path))
                    continue;
                string hash = GoldPatch.HashFile(path);
                if (hash == record[2])
                    continue;
                if (rename != null && hash == rename[3] &&
                    String.Equals(record[1], BinkName, StringComparison.OrdinalIgnoreCase))
                    continue;
                return true;
            }
            return false;
        }

        /// <summary>KOTOR Patch Manager's install holds KMRP's patches and nothing else --
        /// its patch_config.toml, the patch list in kpm_install_state.json (which also
        /// names patches without a module) and the modules in patches\ -- and the
        /// untouched executable can be put back, as KPM's removal would: from KPM's
        /// newest backup when there is one (<paramref name="untouched"/>, which must be
        /// the untouched file), otherwise the file itself, unmodified or with only the
        /// 4 GB flag (<paramref name="untouched"/> empty).</summary>
        private static bool KpmHoldsOnlyKmrp(string targetPath, out string untouched)
        {
            untouched = null;
            try
            {
                string folder = FolderOf(targetPath);
                string config = Path.Combine(folder, ConfigName);
                if (!File.Exists(config))
                    return false;
                List<string> ids = new List<string>();
                foreach (Match match in Regex.Matches(File.ReadAllText(config, Encoding.UTF8),
                             "^\\s*id\\s*=\\s*\"([^\"]*)\"\\s*$", RegexOptions.Multiline | RegexOptions.CultureInvariant))
                    ids.Add(match.Groups[1].Value);
                string state = Path.Combine(folder, KpmStateName);
                if (File.Exists(state))
                {
                    Match list = Regex.Match(File.ReadAllText(state, Encoding.UTF8),
                        "\"InstalledPatches\"\\s*:\\s*\\[([^\\]]*)\\]", RegexOptions.CultureInvariant);
                    if (!list.Success)
                        return false;
                    foreach (Match id in Regex.Matches(list.Groups[1].Value, "\"((?:[^\"\\\\]|\\\\.)*)\""))
                        ids.Add(JsonUnescape(id.Groups[1].Value));
                }
                if (ids.Count == 0 || ids.Exists(id => Array.IndexOf(EnginePatches, id) < 0))
                    return false;
                string patches = Path.Combine(folder, PatchFolder);
                if (Directory.Exists(patches))
                {
                    if (Directory.GetDirectories(patches).Length > 0)
                        return false;
                    foreach (string module in Directory.GetFiles(patches))
                        if (!String.Equals(Path.GetExtension(module), ".dll", StringComparison.OrdinalIgnoreCase) ||
                            Array.IndexOf(EnginePatches, Path.GetFileNameWithoutExtension(module).ToLowerInvariant()) < 0)
                            return false;
                }
                string newest = NewestKpmBackup(targetPath);
                if (newest != null)
                {
                    GameExecutable backup = GameExecutable.Identify(newest);
                    if (backup == null || GoldPatch.HashFile(newest) != backup.Hash)
                        return false;
                    untouched = newest;
                    return true;
                }
                if (GameExecutable.Identify(targetPath) == null)
                    return false;
                untouched = "";
                return true;
            }
            catch (IOException) { return false; }
            catch (UnauthorizedAccessException) { return false; }
        }

        /// <summary>KOTOR Patch Manager's newest backup of the executable, as its
        /// BackupManager finds one (PathHelpers.FindLatestBackup: the name's
        /// yyyyMMdd_HHmmss), or null.</summary>
        private static string NewestKpmBackup(string targetPath)
        {
            string prefix = Path.GetFileName(targetPath) + KpmBackupInfix;
            string newest = null;
            foreach (string path in Directory.GetFiles(FolderOf(targetPath), prefix + "*"))
            {
                string stamp = Path.GetFileName(path).Substring(prefix.Length);
                if (!Regex.IsMatch(stamp, "^[0-9]{8}_[0-9]{6}$"))
                    continue;
                if (newest == null || String.CompareOrdinal(Path.GetFileName(path), Path.GetFileName(newest)) > 0)
                    newest = path;
            }
            return newest;
        }

        /// <summary>What KOTOR Patch Manager's own removal does
        /// (PatchRemover.RemoveAllPatches, KPM 0.7.1), for an install KPM took over with
        /// only KMRP's patches (KpmHoldsOnlyKmrp): the untouched executable back from
        /// KPM's newest backup and that backup deleted, or else the 4 GB flag cleared;
        /// KPM's runtime files and KMRP's modules deleted whatever their contents; and the
        /// proxy deleted, so that UndoEngineChanges puts the game's own binkw32.dll back
        /// (KProxyInstaller.Uninstall). KPM's app files, should it run from the game
        /// folder, are left.</summary>
        private static void RemoveKpmRuntime(string targetPath, string untouched, List<string[]> records,
            Action<string> report)
        {
            string folder = FolderOf(targetPath);
            if (!String.IsNullOrEmpty(untouched))
            {
                string hash = GoldPatch.HashFile(untouched);
                try
                {
                    FileAttributes attributes = File.GetAttributes(targetPath);
                    if ((attributes & FileAttributes.ReadOnly) != 0)
                        File.SetAttributes(targetPath, attributes & ~FileAttributes.ReadOnly);
                    File.Copy(untouched, targetPath, true);
                }
                catch (IOException error)
                {
                    throw new IOException(InUseMessage(targetPath), error);
                }
                catch (UnauthorizedAccessException error)
                {
                    throw new IOException(InUseMessage(targetPath), error);
                }
                if (GoldPatch.HashFile(targetPath) != hash)
                    throw new IOException("Putting back the untouched swkotor.exe from KOTOR Patch Manager's " +
                        "backup could not be verified.");
                File.Delete(untouched);
                if (File.Exists(untouched + ".json"))
                    File.Delete(untouched + ".json");
            }
            else
            {
                string hash = GoldPatch.HashFile(targetPath);
                GameExecutable exe = GameExecutable.ForHash(hash);
                if (exe != null && hash == exe.LargeAddressAwareHash)
                {
                    WriteCharacteristics(targetPath, PeCompatibility.OriginalCharacteristics);
                    if (GoldPatch.HashFile(targetPath) != exe.Hash)
                        throw new IOException("Clearing the 4 GB flag on swkotor.exe could not be verified.");
                }
            }
            foreach (string name in new[] { ConfigName, RuntimeName, "addresses.toml", "addresses.db",
                                            "sqlite3.dll", KpmStateName })
            {
                string path = Path.Combine(folder, name);
                if (File.Exists(path))
                    File.Delete(path);
            }
            foreach (string id in EnginePatches)
            {
                string path = Path.Combine(folder, PatchFolder, id + ".dll");
                if (File.Exists(path))
                    File.Delete(path);
            }
            string[] rename = records.Find(r => r[0] == "moved" && r.Length == 4);
            string moved = Path.Combine(folder, BinkMovedName);
            if (rename != null && File.Exists(moved) && GoldPatch.HashFile(moved) == rename[3])
            {
                string proxy = Path.Combine(folder, BinkName);
                if (File.Exists(proxy))
                    File.Delete(proxy);
            }
            SafeReport(report, "Removed KOTOR Patch Manager's runtime and put back the untouched swkotor.exe.");
        }

        /// <summary>A record of KOTOR Patch Manager's runtime as this install laid it out:
        /// the runtime, its config, its identity file and the backup it restores from,
        /// the modules, the proxy and the rename, and the 4 GB flag KPM's own KMRP patch
        /// sets too.</summary>
        private static bool IsRuntimeRecord(string[] record)
        {
            // The options section is the installed patch's, so it goes with the runtime
            // to whoever owns that now.
            if (record[0] == "moved" || record[0] == "laa" || record[0] == "options")
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

        /// <summary>The patches this install puts in: the one. Its options are chosen
        /// separately (PatchOptions).</summary>
        private static List<string> ChosenPatches()
        {
            return new List<string> { PatchId };
        }

        /// <summary>The patch's options as Advanced Settings has them, in the order its
        /// manifest declares them: id and value. The movie fixes are not among them:
        /// they are part of KMRP, as when they were a patch the installer always chose.</summary>
        internal static KeyValuePair<string, bool>[] PatchOptions()
        {
            return new[]
            {
                new KeyValuePair<string, bool>("controller", KmrpSettings.ControllerSupport),
                new KeyValuePair<string, bool>("map-notes", KmrpSettings.MarkerFixes),
                new KeyValuePair<string, bool>("debug-logs", KmrpSettings.DebugLogs),
            };
        }

        /// <summary>The patch's part of patch_config.toml, as a KOTOR Patch Manager with
        /// patch options writes one: id and module, the hooks that are always installed
        /// and those of each option that is on (Kmrp.engine.hooks and
        /// Kmrp.engine.hooks.&lt;option&gt;, tools/build_native_kpatch.py --config-dir). An
        /// option without hooks of its own, map notes or debug logs, has no resource. The
        /// chosen values are not in this file: they go to configs\kmrp.ini
        /// (WritePatchOptions), where the module reads them. Until 2026-10-04 they were a
        /// [patches.options] table here.</summary>
        internal static string PatchConfigSection(KeyValuePair<string, bool>[] options)
        {
            StringBuilder section = new StringBuilder();
            section.Append("[[patches]]\nid = \"").Append(PatchId).Append("\"\ndll = \"")
                .Append(PatchFolder).Append('/').Append(PatchId).Append(".dll\"\n");
            section.Append(Encoding.UTF8.GetString(ReadResource("Kmrp.engine.hooks")));
            foreach (KeyValuePair<string, bool> option in options)
            {
                if (!option.Value)
                    continue;
                byte[] hooks = TryReadResource("Kmrp.engine.hooks." + option.Key);
                if (hooks != null)
                    section.Append(Encoding.UTF8.GetString(hooks));
            }
            return section.ToString();
        }

        // The patch's own settings file, as KOTOR Patch Manager with patch options lays
        // one out: configs\<patch id>.ini in the game folder. The section below is the
        // record of the option values the patch was applied with, a toggle as 1 or 0;
        // KMRP's module reads it (KmrpOptions.h). Whoever installs the patch writes the
        // section, this installer or KPM, and leaves the rest of the file alone.
        internal const string OptionsFolder = "configs";
        internal const string OptionsName = OptionsFolder + "\\" + PatchId + ".ini";
        internal const string OptionsSection = "Patch Options";
        // Latin-1 maps every byte to one character and back, so whatever else the file
        // holds comes through a rewrite unchanged.
        private static readonly Encoding OptionsEncoding = Encoding.GetEncoding(28591);

        private static string WithoutOptionsSection(string text)
        {
            StringBuilder kept = new StringBuilder();
            bool inSection = false, dropped = false;
            foreach (string line in text.Split('\n'))
            {
                string trimmed = line.Trim();
                if (trimmed.Length >= 2 && trimmed[0] == '[' && trimmed[trimmed.Length - 1] == ']')
                {
                    inSection = String.Equals(trimmed.Substring(1, trimmed.Length - 2).Trim(), OptionsSection,
                        StringComparison.OrdinalIgnoreCase);
                    dropped |= inSection;
                }
                if (!inSection)
                    kept.Append(line).Append('\n');
            }
            if (!dropped)
                return text;
            if (kept.Length > 0)
                kept.Length -= 1;
            return kept.ToString().TrimStart('\r', '\n');
        }

        /// <summary>Writes the [Patch Options] section of configs\kmrp.ini, in place of
        /// the one an earlier install left, and records that this install did.</summary>
        private static void WritePatchOptions(string folder, KeyValuePair<string, bool>[] options,
            List<string[]> records)
        {
            string path = Path.Combine(folder, OptionsName);
            string rest = File.Exists(path) ? WithoutOptionsSection(File.ReadAllText(path, OptionsEncoding)) : "";
            StringBuilder text = new StringBuilder();
            text.Append('[').Append(OptionsSection).Append("]\r\n");
            foreach (KeyValuePair<string, bool> option in options)
                text.Append(option.Key).Append('=').Append(option.Value ? '1' : '0').Append("\r\n");
            if (rest.Length > 0)
                text.Append("\r\n").Append(rest);
            Directory.CreateDirectory(Path.Combine(folder, OptionsFolder));
            File.WriteAllText(path, text.ToString(), OptionsEncoding);
            records.Add(new[] { "options", OptionsName });
        }

        /// <summary>Takes the section out again. A file that held nothing else is
        /// deleted, and the folder once it is empty; anything else in them stays.</summary>
        private static void RemovePatchOptions(string folder, List<string[]> records)
        {
            if (!records.Exists(r => r[0] == "options"))
                return;
            try
            {
                string path = Path.Combine(folder, OptionsName);
                if (File.Exists(path))
                {
                    string text = File.ReadAllText(path, OptionsEncoding);
                    string rest = WithoutOptionsSection(text);
                    if (rest.Trim().Length == 0)
                        File.Delete(path);
                    else if (rest.Length != text.Length)
                        File.WriteAllText(path, rest, OptionsEncoding);
                }
                string directory = Path.Combine(folder, OptionsFolder);
                if (Directory.Exists(directory) && Directory.GetFileSystemEntries(directory).Length == 0)
                    Directory.Delete(directory);
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }

        /// <summary>KOTOR Patch Manager's runtime, the proxy that loads it, KMRP's patch
        /// module and patch_config.toml -- the layout KPM's own proxy deployment gives
        /// a game folder. Every file goes through WriteOwned, which refuses one it did
        /// not write; the game's binkw32.dll is renamed, and recorded, first.</summary>
        private static void InstallEngine(string folder, string exeName, GameExecutable exe, List<string> patches,
            List<string[]> records, Action<string> report)
        {
            WriteOwned(folder, RuntimeName, ReadResource("Kmrp.engine.runtime"), records);
            WriteOwned(folder, KpmLicenseName, ReadResource("Kmrp.engine.license"), records);
            KeyValuePair<string, bool>[] options = PatchOptions();
            Directory.CreateDirectory(Path.Combine(folder, PatchFolder));
            WriteOwned(folder, PatchFolder + "\\" + PatchId + ".dll", PatchModule(), records);
            string config = "target_version_sha = \"" + exe.Hash + "\"\n\n" + PatchConfigSection(options);
            WriteOwned(folder, ConfigName, new UTF8Encoding(false).GetBytes(config), records);
            WritePatchOptions(folder, options, records);
            WriteOwned(folder, KpmStateName, new UTF8Encoding(false).GetBytes(
                KpmState(Path.Combine(folder, exeName), exe, patches)), records);

            // The proxy last, since it is what makes the game load the rest.
            string bink = Path.Combine(folder, BinkName);
            string moved = Path.Combine(folder, BinkMovedName);
            string binkHash = GoldPatch.HashFile(bink);
            File.Move(bink, moved);
            records.Add(new[] { "moved", BinkName, BinkMovedName, binkHash });
            WriteOwned(folder, BinkName, ReadResource("Kmrp.engine.proxy"), records);
            List<string> off = new List<string>();
            foreach (KeyValuePair<string, bool> option in options)
                if (!option.Value && option.Key != "debug-logs")
                    off.Add(option.Key);
            SafeReport(report, "Installed KOTOR Patch Manager's runtime with KMRP's patch" +
                (off.Count == 0 ? ", every option on." : ", without: " + String.Join(", ", off.ToArray()) + "."));
        }

        /// <summary>kpm_install_state.json, as KOTOR Patch Manager 0.7.1 writes it
        /// (ManagedInstallState, schema 1): which executable this was before a patch
        /// changed it, CD 1.03, GOG's or Steam's. KPM knows a game by its executable's hash, and the 4 GB flag
        /// this install sets makes CD 1.03's or GOG's one KPM does not know. KPM's Apply first clears
        /// what is installed -- patch_config.toml, which also names the hash, with it --
        /// and then identifies the game, from this file when the hash is unknown
        /// (GameDetector.DetectVersionFromManagedInstallState). With neither this nor
        /// a backup (WriteKpmBackup), KPM refused every patch over this install on
        /// 2026-09-29, having already removed KMRP's runtime; with this alone, KPM 0.7.1
        /// applied KMRP's patches and another beside them. Where this install set the
        /// flag, the backup lets KPM start from the unmodified file anyway; this is what
        /// identifies an executable that already had the flag, when there is no backup.
        /// It also records the deployment, LibraryProxyInstalled: KPM releases after 0.7.1
        /// keep the method a game's state records on Apply and Launch
        /// (LaneDibello/Kotor-Patch-Manager#283), so pressing Apply in KPM keeps this
        /// install's proxy whatever KPM's "Use library proxy" setting says, and the game
        /// started directly stays patched. That is why Steam's executable gets one too,
        /// though KPM knows its unchanged file by hash: there only the proxy works at all.
        /// Enum values are KPM's (Platform.Windows 0, Distribution.GOG 0 or Steam 1,
        /// Architecture.x86 0, GameTitle.KOTOR1 1), as its table has the three
        /// executables.</summary>
        private static string KpmState(string exePath, GameExecutable exe, List<string> patches)
        {
            string now = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss", CultureInfo.InvariantCulture);
            string hash = exe.Hash;
            string size = exe.Length.ToString(CultureInfo.InvariantCulture);
            string distribution = exe.KpmDistribution.ToString(CultureInfo.InvariantCulture);
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
                "    \"Platform\": 0,\r\n    \"Distribution\": " + distribution + ",\r\n    \"Version\": \"1.0.3\",\r\n" +
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

        /// <summary>Sets IMAGE_FILE_LARGE_ADDRESS_AWARE on CD 1.03's or GOG's swkotor.exe,
        /// the one-bit change the standalone installer also made (PeCompatibility), and
        /// checks the result is the known large-address file; first it leaves a backup
        /// of the unmodified file for KOTOR Patch Manager (WriteKpmBackup). False when
        /// there was nothing to do: the flag already set, by the player or another tool,
        /// is left alone, and restore leaves it too.</summary>
        private static bool SetLargeAddressAware(string targetPath, GameExecutable exe, List<string> patches,
            List<string[]> records, Action<string> report)
        {
            string hash = GoldPatch.HashFile(targetPath);
            if (hash == exe.LargeAddressAwareHash)
            {
                SafeReport(report, "swkotor.exe already has the 4 GB flag.");
                return false;
            }
            if (hash != exe.Hash || exe.LargeAddressAwareHash == null)
                throw new InvalidDataException("swkotor.exe changed during the install. No changes were kept.");
            WriteKpmBackup(targetPath, exe, patches, records);
            WriteCharacteristics(targetPath, PeCompatibility.LargeAddressAwareCharacteristics);
            if (GoldPatch.HashFile(targetPath) != exe.LargeAddressAwareHash)
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
        private static void WriteKpmBackup(string targetPath, GameExecutable exe, List<string> patches,
            List<string[]> records)
        {
            string folder = FolderOf(targetPath);
            string name = Path.GetFileName(targetPath) + KpmBackupInfix +
                DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
            WriteOwned(folder, name, File.ReadAllBytes(targetPath), records);
            if (records[records.Count - 1][2] != exe.Hash)
                throw new InvalidDataException("swkotor.exe changed during the install. No changes were kept.");
            StringBuilder ids = new StringBuilder();
            foreach (string id in patches)
                ids.Append(ids.Length > 0 ? ", " : "").Append('"').Append(id).Append('"');
            string json = "{\r\n" +
                "  \"OriginalPath\": \"" + JsonString(targetPath) + "\",\r\n" +
                "  \"BackupPath\": \"" + JsonString(Path.Combine(folder, name)) + "\",\r\n" +
                "  \"Hash\": \"" + exe.Hash + "\",\r\n" +
                "  \"FileSize\": " + exe.Length.ToString(CultureInfo.InvariantCulture) + ",\r\n" +
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
                string hash = File.Exists(targetPath) ? GoldPatch.HashFile(targetPath) : null;
                GameExecutable exe = hash == null ? null : GameExecutable.ForHash(hash);
                if (exe != null && hash == exe.LargeAddressAwareHash)
                {
                    WriteCharacteristics(targetPath, PeCompatibility.OriginalCharacteristics);
                    if (GoldPatch.HashFile(targetPath) != exe.Hash)
                        throw new IOException("Clearing the 4 GB flag on swkotor.exe could not be verified.");
                }
                else
                    SafeReport(report, "Left swkotor.exe's header alone because it changed after install.");
            }
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

        private static byte[] TryReadResource(string name)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
                return stream == null ? null : ReadResource(name);
        }

        /// <summary>The patch's module, out of the embedded .kpatch, which stores it
        /// uncompressed: the installer carries its 189 MB once, not twice.</summary>
        private static byte[] PatchModule()
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(KpatchResource))
            {
                if (stream == null)
                    throw new InvalidDataException("This build does not carry " + KpatchResource + ".");
                using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read, false))
                {
                    ZipArchiveEntry entry = zip.GetEntry(KpatchModuleEntry);
                    if (entry == null)
                        throw new InvalidDataException("KMRP's patch carries no module.");
                    using (Stream module = entry.Open())
                    using (MemoryStream copy = new MemoryStream((int)entry.Length))
                    {
                        module.CopyTo(copy);
                        return copy.ToArray();
                    }
                }
            }
        }

        // ------------------------------------------------------------ owned files

        // The manifest's rows, each a tab-separated record kept as-is in memory:
        //   file   <name> <SHA-256>          a file this install wrote; name may be
        //                                    under patches\
        //   moved  <from> <to> <SHA-256>     a game file renamed (binkw32.dll)
        //   laa    set                       this install set the 4 GB flag
        //   options <name>                   this install wrote the [Patch Options]
        //                                    section of configs\kmrp.ini
        //   kpatch <full path> <SHA-256> created|replaced
        //                                    one of KMRP's .kpatch files, for KOTOR
        //                                    Patch Manager's app (DeliverKpatches)
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

        // ------------------------------------------------------------ KMRP's .kpatch files

        /// <summary>Puts KMRP's .kpatch file where KOTOR Patch Manager's app finds
        /// them, so the installer is the one file a player needs: KPM's patch folder, when
        /// its settings name one (KpmPatchesFolder), for either kind of install; otherwise,
        /// for an install for KPM only, a "KPM patches" folder in the game folder, with the
        /// README and KPM's licence, which the installer then points the player to.
        /// Returns where they went, or null. Each file is recorded (WriteKpatch); a file
        /// that could not be written into KPM's folder falls back to the game folder for
        /// an install for KPM, and is only reported otherwise.</summary>
        private static string DeliverKpatches(string gameFolder, bool forPatchManager, List<string[]> records,
            Action<string> report)
        {
            string kpm = KpmPatchesFolder();
            if (kpm != null)
            {
                try
                {
                    WriteKpatches(kpm, false, records, report);
                    return kpm;
                }
                catch (IOException error)
                {
                    SafeReport(report, "KMRP's patches could not be added to KOTOR Patch Manager's patch " +
                        "folder (" + kpm + "): " + error.Message);
                }
                catch (UnauthorizedAccessException error)
                {
                    SafeReport(report, "KMRP's patches could not be added to KOTOR Patch Manager's patch " +
                        "folder (" + kpm + "): " + error.Message);
                }
            }
            if (!forPatchManager)
                return null;
            string folder = Path.Combine(gameFolder, KpatchFolderName);
            Directory.CreateDirectory(folder);
            WriteKpatches(folder, true, records, report);
            return folder;
        }

        private static void WriteKpatches(string folder, bool withReadme, List<string[]> records, Action<string> report)
        {
            for (int i = 0; i < Kpatches.GetLength(0); i++)
                WriteKpatch(Path.Combine(folder, Kpatches[i, 0]), ReadResource(KpatchResource),
                    Kpatches[i, 1], records, report);
            if (!withReadme)
                return;
            WriteKpatch(Path.Combine(folder, KpatchReadmeName), ReadResource("Kmrp.kpatch.readme"), null, records, report);
            WriteKpatch(Path.Combine(folder, KpatchLicenseName), ReadResource("Kmrp.engine.license"), null, records, report);
        }

        /// <summary>One file of the set, recorded "created" when it was not there, which
        /// restore removes while it is as written, or "replaced" when it was, which restore
        /// leaves: an older copy of the same KMRP patch (its manifest's id, `patchId`) is
        /// brought up to this version, since KMRP's module refuses another version's data
        /// file, but a file the player had is never deleted. A file of the same name that is
        /// not KMRP's is left alone, and said so.</summary>
        private static void WriteKpatch(string path, byte[] data, string patchId, List<string[]> records,
            Action<string> report)
        {
            string state = "created";
            if (File.Exists(path))
            {
                bool same = GoldPatch.HashFile(path) == HashBytes(data);
                if (!same && (patchId == null || KpatchId(path) != patchId))
                {
                    SafeReport(report, "Left " + path + " alone: it is not KMRP's.");
                    return;
                }
                state = "replaced";
                if (same)
                {
                    records.Add(new[] { "kpatch", path, HashBytes(data), state });
                    return;
                }
            }
            File.WriteAllBytes(path, data);
            records.Add(new[] { "kpatch", path, GoldPatch.HashFile(path), state });
        }

        /// <summary>Removes the .kpatch files this install created, while they are as
        /// written, and the game folder's "KPM patches" folder once it is empty.</summary>
        private static void RemoveKpatches(List<string[]> records, Action<string> report)
        {
            foreach (string[] record in records)
            {
                if (record[0] != "kpatch" || record[3] != "created" || !File.Exists(record[1]))
                    continue;
                if (GoldPatch.HashFile(record[1]) != record[2])
                {
                    SafeReport(report, "Left " + record[1] + " in place because it changed after install.");
                    continue;
                }
                File.Delete(record[1]);
                string folder = Path.GetDirectoryName(record[1]);
                try
                {
                    if (String.Equals(Path.GetFileName(folder), KpatchFolderName, StringComparison.OrdinalIgnoreCase) &&
                        Directory.Exists(folder) && Directory.GetFileSystemEntries(folder).Length == 0)
                        Directory.Delete(folder);
                }
                catch { }
            }
        }

        /// <summary>A path a kpatch row may name: absolute, and KMRP's .kpatch file or one
        /// of the three an older install put beside it, or the README or licence in a "KPM patches" folder. Restore deletes
        /// what these rows name, so nothing else is accepted.</summary>
        private static bool IsKpatchPath(string path)
        {
            try
            {
                if (String.IsNullOrEmpty(path) || !Path.IsPathRooted(path) ||
                    path.IndexOfAny(Path.GetInvalidPathChars()) >= 0)
                    return false;
                string name = Path.GetFileName(path);
                for (int i = 0; i < Kpatches.GetLength(0); i++)
                    if (String.Equals(name, Kpatches[i, 0], StringComparison.OrdinalIgnoreCase))
                        return true;
                foreach (string retired in RetiredKpatchNames)
                    if (String.Equals(name, retired, StringComparison.OrdinalIgnoreCase))
                        return true;
                return (String.Equals(name, KpatchReadmeName, StringComparison.OrdinalIgnoreCase) ||
                        String.Equals(name, KpatchLicenseName, StringComparison.OrdinalIgnoreCase)) &&
                    String.Equals(Path.GetFileName(Path.GetDirectoryName(path)), KpatchFolderName,
                        StringComparison.OrdinalIgnoreCase);
            }
            catch { return false; }
        }

        // KOTOR Patch Manager's settings file (KPatchLauncher AppSettings in KPM 0.7.1).
        private static string KpmSettingsPath()
        {
            return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "KPatchLauncher", "settings.json");
        }

        /// <summary>The patch folder KOTOR Patch Manager's app uses, from its settings
        /// (%APPDATA%\KPatchLauncher\settings.json, "PatchesPath", KPatchLauncher
        /// AppSettings in KPM 0.7.1), or null when KPM has none on this PC or it no longer
        /// exists.</summary>
        private static string KpmPatchesFolder()
        {
            try
            {
                string settings = KpmSettingsPath();
                if (!File.Exists(settings))
                    return null;
                Match match = Regex.Match(File.ReadAllText(settings, Encoding.UTF8),
                    "\"PatchesPath\"\\s*:\\s*\"((?:[^\"\\\\]|\\\\.)*)\"", RegexOptions.CultureInvariant);
                if (!match.Success)
                    return null;
                string path = JsonUnescape(match.Groups[1].Value);
                return path.Length > 0 && Path.IsPathRooted(path) && Directory.Exists(path)
                    ? Path.GetFullPath(path) : null;
            }
            catch { return null; }
        }

        /// <summary>A JSON string's contents unescaped. KPM writes its settings with
        /// System.Text.Json, which escapes every backslash and, by default, every character
        /// outside ASCII as \uXXXX.</summary>
        private static string JsonUnescape(string value)
        {
            StringBuilder text = new StringBuilder();
            for (int i = 0; i < value.Length; i++)
            {
                char c = value[i];
                if (c != '\\' || i + 1 >= value.Length)
                {
                    text.Append(c);
                    continue;
                }
                char next = value[++i];
                if (next == 'u' && i + 4 < value.Length)
                {
                    text.Append((char)Int32.Parse(value.Substring(i + 1, 4), NumberStyles.HexNumber,
                        CultureInfo.InvariantCulture));
                    i += 4;
                }
                else if (next == 'n') text.Append('\n');
                else if (next == 'r') text.Append('\r');
                else if (next == 't') text.Append('\t');
                else if (next == 'b') text.Append('\b');
                else if (next == 'f') text.Append('\f');
                else text.Append(next);
            }
            return text.ToString();
        }

        /// <summary>The id in a .kpatch file's manifest.toml, or null.</summary>
        private static string KpatchId(string path)
        {
            try
            {
                using (ZipArchive zip = new ZipArchive(File.OpenRead(path), ZipArchiveMode.Read, false))
                {
                    ZipArchiveEntry manifest = zip.GetEntry("manifest.toml");
                    if (manifest == null)
                        return null;
                    using (StreamReader reader = new StreamReader(manifest.Open(), Encoding.UTF8))
                    {
                        Match id = Regex.Match(reader.ReadToEnd(), "(?m)^\\s*id\\s*=\\s*\"([^\"]+)\"",
                            RegexOptions.CultureInvariant);
                        return id.Success ? id.Groups[1].Value : null;
                    }
                }
            }
            catch { return null; }
        }

        private static string HashBytes(byte[] data)
        {
            using (System.Security.Cryptography.SHA256 sha = System.Security.Cryptography.SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(data)).Replace("-", "");
        }

        /// <summary>KMRP's .kpatch file, its README and KPM's licence, written to
        /// `folder` for sharing on their own (the installer's --export-kpm-patches). Not
        /// recorded anywhere: it is not an install.</summary>
        internal static void ExportKpatches(string folder)
        {
            Directory.CreateDirectory(folder);
            for (int i = 0; i < Kpatches.GetLength(0); i++)
                File.WriteAllBytes(Path.Combine(folder, Kpatches[i, 0]), ReadResource(KpatchResource));
            File.WriteAllBytes(Path.Combine(folder, KpatchReadmeName), ReadResource("Kmrp.kpatch.readme"));
            File.WriteAllBytes(Path.Combine(folder, KpatchLicenseName), ReadResource("Kmrp.engine.license"));
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
                        (parts.Length == 2 && parts[0] == "laa") ||
                        (parts.Length == 2 && parts[0] == "options" && parts[1] == OptionsName) ||
                        (parts.Length == 4 && parts[0] == "kpatch" && IsKpatchPath(parts[1]) &&
                         (parts[3] == "created" || parts[3] == "replaced")))
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
