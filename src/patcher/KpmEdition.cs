using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

namespace Kmrp
{
    /// <summary>When the commit this installer was built from was made, in CEST
    /// (UTC+02:00, all year): build_kmrp.ps1 takes it from git and embeds it as
    /// Kmrp.build.stamp. Everyone who builds a commit gets the same date and every later
    /// commit a later one, so an installed KMRP, whose manifest records its date
    /// ("built"), can be told older or newer than this installer whether or not the
    /// version was raised (the maintainer, 2026-10-19). Dates are compared as moments,
    /// so the zone they are written in cannot change the answer.</summary>
    internal static class BuildStamp
    {
        private const string Format = "yyyy-MM-dd'T'HH:mm:sszzz";
        private static readonly TimeSpan Cest = TimeSpan.FromHours(2);
        private static bool read;
        private static DateTimeOffset? own;

        /// <summary>This installer's date; null for a build without one.</summary>
        internal static DateTimeOffset? Current
        {
            get
            {
                if (!read)
                {
                    read = true;
                    try
                    {
                        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Kmrp.build.stamp"))
                        {
                            DateTimeOffset when;
                            if (stream != null && TryParse(new StreamReader(stream, Encoding.ASCII).ReadToEnd().Trim(), out when))
                                own = when;
                        }
                    }
                    catch { }
                }
                return own;
            }
        }

        internal static bool TryParse(string text, out DateTimeOffset when)
        {
            return DateTimeOffset.TryParseExact(text ?? String.Empty, Format, CultureInfo.InvariantCulture,
                DateTimeStyles.None, out when);
        }

        /// <summary>As the manifest records it: 2026-10-19T12:52:14+02:00.</summary>
        internal static string Text(DateTimeOffset when)
        {
            return when.ToOffset(Cest).ToString(Format, CultureInfo.InvariantCulture);
        }

        /// <summary>As the window shows it: 19 Oct 2026, 12:52 CEST.</summary>
        internal static string Display(DateTimeOffset when)
        {
            return when.ToOffset(Cest).ToString("d MMM yyyy, HH:mm", CultureInfo.InvariantCulture) + " CEST";
        }
    }

    /// <summary>KMRP's install, on KOTOR Patch Manager's runtime.
    ///
    /// KMRP's installer does not rewrite swkotor.exe: the executable changes are
    /// KMRP's own KPM patch, "kmrp" (tools/build_native_kpatch.py), whose module
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
        // In KMRP's folder since 2026-10-20 (KmrpFolder); kmrp-kotor-patch-manager-LICENSE.txt
        // in the game folder until then.
        private const string KpmLicenseName = KmrpFolder.KpmLicense;
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
        // since 2026-10-04: the module carries every resolution's files (since 2026-10-19
        // the art pack beside it does, PackName), the controller
        // and SDL, and controller support and map notes are its options.
        // Until then there were four, KMRP with KMRP Controller, KMRP Movies and KMRP Map
        // Notes beside it; their names are still accepted in an older install's records
        // (IsKpatchPath), so that restore can remove them.
        //
        // Since 2026-10-05 KMRP is two patches again, by the maintainer's decision: its
        // own, and the controller patch beside it, "KOTOR 1 Native Controller Mod +
        // Xbox HUD" (id kmrp-controller, tools/build_controller_kpatch.py), which also
        // works on a game without KMRP. KMRP's patch has no controller code of its own
        // and no controller option, and neither patch needs the other. Controller
        // Support in Advanced Settings decides whether this installer installs the
        // controller patch and delivers its .kpatch (the maintainer's direction,
        // 2026-10-05; for an hour that day both were always installed).
        // (The id was the controller add-on of the four-patch edition until
        // 2026-10-04, and for a day one that restore removed as retired.)
        private const string PatchId = "kmrp";
        private const string ControllerPatchId = "kmrp-controller";
        private const string KpatchResource = "Kmrp.kpatch";
        private const string ControllerKpatchResource = "KmrpController.kpatch";
        // D3M0's High FPS Fixes (MIT), a third patch since 2026-10-09, installed only
        // while High FPS Fix is on in Advanced Settings (off by default). It is the
        // author's own file, unchanged (third_party/Included/HighFpsFixes-1.0.1 by
        // D3M0); its hooks for patch_config.toml are made from it by
        // tools/build_bundled_kpatch_config.py, which also holds it against both of
        // KMRP's patches for overlaps.
        private const string HighFpsPatchId = "high-fps-fixes";
        private const string HighFpsKpatchResource = "KmrpHighFps.kpatch";
        // ShaeMyName's K1 Marked Empty Containers (in KOTOR Patch Manager's repository,
        // MIT), a fourth patch since 2026-10-19 (issue 43), installed while Marked Empty
        // Containers is on in Advanced Settings, the default. The .kpatch as KPM 0.7.1's
        // release ships it (third_party/Included/K1MarkedEmptyContainers-1.0.0 by
        // ShaeMyName): one replace hook and no module, so its patch_config.toml section
        // names no DLL, as KPM's own PatchApplicator writes it, and nothing of it goes
        // into patches\.
        private const string EmptyContainersPatchId = "k1-marked-empty-containers";
        private const string EmptyContainersKpatchResource = "KmrpEmptyContainers.kpatch";
        // Synchro's K1 Modern Driver Compatibility (MPL-2.0), a fifth patch since 2026-10-31
        // (issue 44), installed while Modern Driver Compatibility is on in Advanced Settings,
        // the default, where its module can run (InstallPlatform.DriverCompatMissing). The
        // .kpatch as its author releases it (third_party/Included/k1-modern-driver-
        // compatibility-2.0.1 by Synchro), its hooks made for patch_config.toml and held
        // against KMRP's patches by tools/build_bundled_kpatch_config.py like the two above.
        // Loaded by KOTOR Patch Manager's proxy, it needs no Wine DLL override under Proton,
        // which its standalone dinput8.dll, what KMRP installed until then, did.
        private const string DriverCompatPatchId = "k1-modern-driver-compatibility";
        private const string DriverCompatKpatchResource = "KmrpDriverCompat.kpatch";
        private const string DriverCompatVersion = "2.0.1";
        // The standalone build's payload: one of these beside the game that KMRP did not
        // put there means the player runs K1DC their own way, and the two would patch the
        // same places, so KMRP leaves its copy out (its author: use only one of the two).
        private const string StandaloneDriverCompatName = "k1-modern-driver-compatibility.asi";
        private const string KpatchModuleEntry = "binaries/windows_x86.dll";
        // KMRP's art pack (tools/kmrp_pack.py), embedded as Kmrp.assets.pack and written
        // into patches\ beside the module, which reads it there. KOTOR Patch Manager
        // removes only the modules in that folder, so the pack outlives KPM switching the
        // patch off and on. Since 2026-10-19: until then the art was a bank inside the
        // module, and the installer was twice the size.
        private const string PackName = "kmrp-assets.pack";
        private const string PackResource = "Kmrp.assets.pack";
        // File name, patch id, embedded resource, the resource prefix of its hooks.
        private static readonly string[,] Kpatches =
        {
            { "KMRP.kpatch", PatchId, KpatchResource, "Kmrp.engine.hooks" },
            { "KOTOR 1 Native Controller Mod + Xbox HUD.kpatch", ControllerPatchId, ControllerKpatchResource,
              "KmrpController.engine.hooks" },
            { "HighFpsFixes.kpatch", HighFpsPatchId, HighFpsKpatchResource, "KmrpHighFps.engine.hooks" },
            { "K1MarkedEmptyContainers.kpatch", EmptyContainersPatchId, EmptyContainersKpatchResource,
              "KmrpEmptyContainers.engine.hooks" },
            { "k1-modern-driver-compatibility.kpatch", DriverCompatPatchId, DriverCompatKpatchResource,
              "KmrpDriverCompat.engine.hooks" },
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
            { "kmrp", "kmrp-movies", "kmrp-map-notes", "kmrp-controller", "high-fps-fixes", "k1-marked-empty-containers",
              "k1-modern-driver-compatibility" };
        // ------------------------------------------------------------ state

        // KMRP\kpm.manifest (KmrpFolder); KMRP_KPM.manifest in the game folder until 2026-10-20.
        internal static string ManifestPath(string executablePath)
        {
            return KmrpFolder.PathOf(executablePath, KmrpFolder.KpmManifest);
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

        /// <summary>The date of the build installed here, as its manifest records it;
        /// null when nothing is installed or the install is from before builds were
        /// dated (2026-10-19).</summary>
        internal static DateTimeOffset? InstalledBuild(string executablePath)
        {
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(executablePath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    DateTimeOffset when;
                    if (parts.Length == 2 && parts[0] == "built" && BuildStamp.TryParse(parts[1], out when))
                        return when;
                }
            }
            catch { }
            return null;
        }

        /// <summary>How the KMRP installed here stands against this installer: -1 older
        /// (an undated install, and one by the standalone installer, always are), 0 the
        /// same build, 1 newer; null when nothing is installed or this installer has no
        /// date.</summary>
        internal static int? CompareInstalled(string targetPath)
        {
            DateTimeOffset? mine = BuildStamp.Current;
            if (mine == null)
                return null;
            if (IsStandaloneInstall(targetPath))
                return -1;
            if (!IsInstalled(targetPath))
                return null;
            if (NeedsRepair(targetPath) != null)
                return -1;
            DateTimeOffset? theirs = InstalledBuild(targetPath);
            if (theirs == null)
                return -1;
            int order = theirs.Value.CompareTo(mine.Value);
            return order < 0 ? -1 : order > 0 ? 1 : 0;
        }

        /// <summary>Why the install recorded here is not what the game will run, in the
        /// player's words, or null when it is, or when nothing is installed. The manifest
        /// alone said "Patched successfully" until 2026-11-01, after Steam's file check had
        /// put its own binkw32.dll back and KMRP no longer loaded (audit INS-07). A file
        /// that is there but different is not asked about: KPM's Apply rewrites them, and
        /// a player's edits are theirs. An install KPM has taken over is KPM's to keep
        /// whole. The window offers the same install as a Repair.</summary>
        internal static string NeedsRepair(string targetPath)
        {
            try
            {
                targetPath = Path.GetFullPath(targetPath);
                if (!IsInstalled(targetPath))
                    return null;
                if (ManifestDamage(targetPath) != null)
                    return "KMRP's record of this install is damaged.";
                if (Array.IndexOf(File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8), IncompleteRow) >= 0)
                    return "An install did not finish. Repair finishes it.";
                string folder = FolderOf(targetPath);
                List<string[]> records = ReadRecords(targetPath);
                if (RuntimeChangedSinceInstall(folder, records))
                    return null;
                string[] rename = records.Find(r => r[0] == "moved" && r.Length == 4);
                string bink = GamePath.Combine(folder, BinkName);
                if (rename != null && File.Exists(bink) && GoldPatch.HashFile(bink) == rename[3])
                    return "The game's own binkw32.dll is back (Steam's file check puts it back), " +
                        "so KMRP is not loading. Repair installs it again.";
                foreach (string[] record in records)
                    if (record[0] == "file" && record[1] != KmrpFolder.ControllerSettings &&
                        !File.Exists(GamePath.Combine(folder, record[1])))
                        return record[1] + " is missing. Repair installs it again.";
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            return null;
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
                    ? "KMRP is installed. KOTOR Patch Manager manages this game and loads KMRP's patch."
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

        // ------------------------------------------------------------ settings

        // The Advanced Settings an install was made with, one manifest row since 2026-11-10:
        // "settings <key>=<1|0>,...". ReadRecords skips it, as it skips every row it does not
        // act on, and an older installer does the same. Keys, then the names the settings
        // page gives them.
        private const string SettingsRow = "settings";
        private static readonly string[] SettingKeys =
            { "controller", "driver-compatibility", "map-notes", "hd-icons", "high-fps", "empty-containers", "debug-logs" };
        private static readonly string[] SettingNames =
            { "Native Controller Support", "Modern Driver Compatibility", "Area Map Marker Fixes", "HD Item Icons",
              "High FPS Fix", "Marked Empty Containers", "Debug Logs" };

        private static bool[] SettingValues()
        {
            return new[] { KmrpSettings.ControllerSupport, KmrpSettings.DriverCompatibility, KmrpSettings.MarkerFixes,
                           KmrpSettings.HdIcons, KmrpSettings.HighFpsFix, KmrpSettings.MarkedEmptyContainers,
                           KmrpSettings.DebugLogs };
        }

        private static string[] SettingsRecord()
        {
            bool[] values = SettingValues();
            StringBuilder text = new StringBuilder();
            for (int i = 0; i < SettingKeys.Length; i++)
                text.Append(i > 0 ? "," : "").Append(SettingKeys[i]).Append('=').Append(values[i] ? '1' : '0');
            return new[] { SettingsRow, text.ToString() };
        }

        /// <summary>The settings the install here was made with, by key: its settings row, or,
        /// for an install from before installs recorded them, what its files say
        /// (SettingsFromFiles); null when nothing is installed or neither can be read.</summary>
        private static Dictionary<string, bool> InstalledSettings(string targetPath)
        {
            return RecordedSettings(targetPath) ?? SettingsFromFiles(targetPath);
        }

        /// <summary>The settings of an install without a settings row, read from what it put
        /// in: the patches patch_config.toml names, the [Patch Options] of configs\kmrp.ini,
        /// and the Advanced Settings that have no file of their own taken as they are now.
        /// Only for KMRP's own install with its patch_config.toml as written; null otherwise.
        /// Until later on 2026-11-10 an install without the row offered nothing, so the
        /// maintainer's game, installed that morning, showed Restore Original alone.</summary>
        private static Dictionary<string, bool> SettingsFromFiles(string targetPath)
        {
            try
            {
                if (!IsInstalled(targetPath))
                    return null;
                string folder = FolderOf(targetPath);
                List<string[]> records = ReadRecords(targetPath);
                if (!records.Exists(r => r[0] == "moved") || !OwnedAsWritten(folder, records, ConfigName))
                    return null;
                List<string> ids = ConfiguredPatches(folder);
                Dictionary<string, bool> settings = new Dictionary<string, bool>();
                settings["controller"] = ids.Contains(ControllerPatchId);
                settings["high-fps"] = ids.Contains(HighFpsPatchId);
                settings["empty-containers"] = ids.Contains(EmptyContainersPatchId);
                // K1DC as its Windows 7 and 8 build is not one of the patches.
                settings["driver-compatibility"] = ids.Contains(DriverCompatPatchId) ||
                    (KmrpSettings.DriverCompatibility && InstallPlatform.DriverCompatMissing() != null);
                string options = GamePath.Combine(folder, OptionsName);
                string text = File.Exists(options) ? File.ReadAllText(options, OptionsEncoding) : "";
                foreach (KeyValuePair<string, bool> option in PatchOptions())
                {
                    Match value = Regex.Match(text, "^\\s*" + Regex.Escape(option.Key) + "\\s*=\\s*([01])\\s*$",
                        RegexOptions.Multiline | RegexOptions.CultureInvariant);
                    settings[option.Key] = value.Success ? value.Groups[1].Value == "1" : option.Key != "debug-logs";
                }
                return settings;
            }
            catch (IOException) { return null; }
            catch (UnauthorizedAccessException) { return null; }
        }

        private static Dictionary<string, bool> RecordedSettings(string targetPath)
        {
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length != 2 || parts[0] != SettingsRow)
                        continue;
                    Dictionary<string, bool> settings = new Dictionary<string, bool>();
                    foreach (string pair in parts[1].Split(','))
                    {
                        string[] value = pair.Split('=');
                        if (value.Length == 2)
                            settings[value[0]] = value[1] == "1";
                    }
                    return settings;
                }
            }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
            return null;
        }

        /// <summary>The Advanced Settings that differ from the install here, in the settings
        /// page's words ("High FPS Fix on, Debug Logs off"); null when none does, when
        /// nothing is installed, or when the install does not record its settings (one from
        /// before 2026-11-10, which an install of this build replaces).</summary>
        internal static string ChangedSettings(string targetPath)
        {
            Dictionary<string, bool> installed = InstalledSettings(targetPath);
            if (installed == null)
                return null;
            bool[] values = SettingValues();
            List<string> changed = new List<string>();
            for (int i = 0; i < SettingKeys.Length; i++)
            {
                bool was;
                if (!installed.TryGetValue(SettingKeys[i], out was) || was != values[i])
                    changed.Add(SettingNames[i] + (values[i] ? " on" : " off"));
            }
            return changed.Count == 0 ? null : String.Join(", ", changed.ToArray());
        }

        /// <summary>Applies the Advanced Settings to the install here without installing
        /// again (the maintainer, 2026-11-10: changing a setting "should not install the
        /// whole thing again", only switch that one on or off). Only what a setting owns
        /// changes: a patch's module in patches\ and its .kpatch in KOTOR Patch Manager's
        /// folder, added or taken out; patch_config.toml, the [Patch Options] sections and
        /// kpm_install_state.json written again; for High FPS Fix, the frame-rate keys of
        /// swkotor.ini. KOTOR Patch Manager's runtime, the proxy, the art pack, the art
        /// already made and the swkotor.ini backup stay. The manifest is marked incomplete
        /// while this runs, so a change stopped halfway is one the window offers to Repair.
        /// Where the quick change cannot be made (QuickApplyRefusal), the whole install is
        /// made instead, with the settings chosen now, and the report says why.</summary>
        internal static void ApplySettings(string targetPath, Action<string> report, Action<int, string> progress)
        {
            targetPath = Path.GetFullPath(targetPath);
            using (InstallGuard.Take(targetPath))
            {
                string refusal = QuickApplyRefusal(targetPath);
                if (refusal == null)
                {
                    ApplySettingsCore(targetPath, report, progress);
                    return;
                }
                SafeReport(report, refusal + " Installing again instead, with the settings chosen now.");
            }
            int width, height;
            if (!TryReadInstalledResolution(targetPath, out width, out height))
            {
                width = IniOperations.DefaultWidth;
                height = IniOperations.DefaultHeight;
            }
            Install(targetPath, width, height, report, progress);
        }

        /// <summary>Why the settings cannot be applied in place here, or null when they can.</summary>
        private static string QuickApplyRefusal(string targetPath)
        {
            if (!IsInstalled(targetPath) || IsStandaloneInstall(targetPath))
                return "KMRP's own install is not here.";
            if (ManifestDamage(targetPath) != null || NeedsRepair(targetPath) != null)
                return "The install needs a repair.";
            if (CompareInstalled(targetPath) != 0)
                return "The KMRP installed here is another build.";
            if (InstalledSettings(targetPath) == null)
                return "The install here does not record its settings.";
            string folder = FolderOf(targetPath);
            List<string[]> records = ReadRecords(targetPath);
            if (!records.Exists(r => r[0] == "moved"))
                return "KOTOR Patch Manager manages this game.";
            if (RuntimeChangedSinceInstall(folder, records))
                return "KOTOR Patch Manager has changed the install since.";
            if (GameExecutable.Identify(targetPath) == null)
                return "swkotor.exe is not a version KMRP knows.";
            // K1DC's build for Windows 7 and 8, or a copy of the player's own, is not one
            // of the patches; switching it is the whole install's (DriverCompatRoute).
            bool driverWas;
            InstalledSettings(targetPath).TryGetValue("driver-compatibility", out driverWas);
            if (driverWas != KmrpSettings.DriverCompatibility &&
                (InstallPlatform.DriverCompatMissing() != null ||
                 File.Exists(GamePath.Combine(folder, StandaloneDriverCompatName))))
                return "Modern Driver Compatibility is installed outside KOTOR Patch Manager on this PC.";
            foreach (string name in new[] { ConfigName, KpmStateName })
                if (!OwnedAsWritten(folder, records, name))
                    return name + " changed since it was installed.";
            // A module that stays must be this installer's own: patch_config.toml is written
            // from this installer's hook tables, and a hook naming a function the installed
            // module lacks is lost (2026-09-25, 23 hooks). Builds of one commit share a build
            // date, so CompareInstalled can call two of them the same (2026-11-10).
            List<string> now = ChosenPatches(folder, null);
            for (int i = 0; i < Kpatches.GetLength(0); i++)
            {
                string module = PatchFolder + "\\" + Kpatches[i, 1] + ".dll";
                string path = GamePath.Combine(folder, module);
                if (!now.Contains(Kpatches[i, 1]) || !File.Exists(path))
                    continue;
                byte[] mine = PatchModule(Kpatches[i, 2], false);
                if (mine != null && GoldPatch.HashFile(path) != HashBytes(mine))
                    return module + " is not this installer's.";
            }
            // A module to take out must be the one installed, or it would stay behind.
            foreach (string id in ConfiguredPatches(folder))
            {
                string module = PatchFolder + "\\" + id + ".dll";
                if (!now.Contains(id) && records.Exists(r => r[0] == "file" && r[1] == module) &&
                    !OwnedAsWritten(folder, records, module))
                    return module + " changed since it was installed.";
            }
            return null;
        }

        /// <summary>The file `name` is recorded and still as written.</summary>
        private static bool OwnedAsWritten(string folder, List<string[]> records, string name)
        {
            string[] row = records.Find(r => r[0] == "file" && String.Equals(r[1], name, StringComparison.OrdinalIgnoreCase));
            string path = GamePath.Combine(folder, name);
            return row != null && File.Exists(path) && GoldPatch.HashFile(path) == row[2];
        }

        /// <summary>A file this install wrote, written again: the row's hash follows the new
        /// file. Refused when the file changed since it was written, which ApplySettings
        /// checks first for the two it always writes.</summary>
        private static void RewriteOwned(string folder, string name, byte[] data, InstallJournal records)
        {
            if (!OwnedAsWritten(folder, records.Rows, name))
                throw new IOException(name + " changed since it was installed, so it was left alone.");
            WriteWhole(GamePath.Combine(folder, name), data, delegate(string hash)
            {
                records.Remove(r => r[0] == "file" && String.Equals(r[1], name, StringComparison.OrdinalIgnoreCase));
                records.Add(new[] { "file", name, hash });
            });
        }

        /// <summary>The patch ids patch_config.toml names, in its order.</summary>
        private static List<string> ConfiguredPatches(string folder)
        {
            List<string> ids = new List<string>();
            foreach (string line in File.ReadAllLines(GamePath.Combine(folder, ConfigName), Encoding.UTF8))
            {
                Match id = Regex.Match(line, "^\\s*id\\s*=\\s*\"([^\"]+)\"\\s*$", RegexOptions.CultureInvariant);
                if (id.Success)
                    ids.Add(id.Groups[1].Value);
            }
            return ids;
        }

        private static void ApplySettingsCore(string targetPath, Action<string> report, Action<int, string> progress)
        {
            SafeProgress(progress, 5, "Applying the settings…");
            string folder = FolderOf(targetPath);
            GameExecutable exe = GameExecutable.Identify(targetPath);
            int width, height;
            if (!TryReadInstalledResolution(targetPath, out width, out height))
                throw new InvalidDataException("KMRP's record of this install has no resolution. Use Repair.");
            string changed = ChangedSettings(targetPath);
            Dictionary<string, bool> before = InstalledSettings(targetPath);
            List<string> was = ConfiguredPatches(folder);
            List<string> now = ChosenPatches(folder, report);
            InstallJournal records = new InstallJournal(targetPath, width, height, ReadRecords(targetPath));
            string kpm = KpmPatchesFolder();
            List<string> taken = new List<string>(), added = new List<string>();
            try
            {
                for (int i = 0; i < Kpatches.GetLength(0); i++)
                {
                    string id = Kpatches[i, 1];
                    if (id == PatchId || was.Contains(id) == now.Contains(id))
                        continue;
                    string module = PatchFolder + "\\" + id + ".dll";
                    string kpatch = kpm == null ? null : GamePath.Combine(kpm, Kpatches[i, 0]);
                    if (was.Contains(id))
                    {
                        // Out: its module while it is as written, its .kpatch where this
                        // install created it, and the controller patch's options section.
                        List<string[]> mine = records.Rows.FindAll(r =>
                            (r[0] == "file" && String.Equals(r[1], module, StringComparison.OrdinalIgnoreCase)) ||
                            (r[0] == "kpatch" && r.Length == 4 && String.Equals(Path.GetFileName(r[1]), Kpatches[i, 0],
                                StringComparison.OrdinalIgnoreCase)) ||
                            (id == ControllerPatchId && r[0] == "options" && r[1] == ControllerOptionsName));
                        RemoveOwned(folder, mine, report);
                        RemoveKpatches(mine, report);
                        RemovePatchOptions(folder, mine);
                        records.Remove(r => mine.Contains(r));
                        taken.Add(id);
                    }
                    else
                    {
                        byte[] data = PatchModule(Kpatches[i, 2], id != EmptyContainersPatchId);
                        if (data != null)
                            WriteOwned(folder, module, data, records);
                        if (kpatch != null)
                        {
                            bool theirs = id == HighFpsPatchId || id == EmptyContainersPatchId || id == DriverCompatPatchId;
                            records.Remove(r => r[0] == "kpatch" && String.Equals(r[1], kpatch, StringComparison.OrdinalIgnoreCase));
                            WriteKpatch(kpatch, ReadResource(Kpatches[i, 2]), theirs ? null : id, records, report);
                        }
                        added.Add(id);
                    }
                }
                SafeProgress(progress, 40, "Writing the patches' settings…");
                RewriteOwned(folder, ConfigName, new UTF8Encoding(false).GetBytes(PatchConfig(exe, now)), records);
                records.Remove(r => r[0] == "options");
                WritePatchOptions(folder, OptionsName, PatchOptions(), records);
                if (now.Contains(ControllerPatchId))
                    WritePatchOptions(folder, ControllerOptionsName, ControllerPatchOptions(), records);
                RewriteOwned(folder, KpmStateName, new UTF8Encoding(false).GetBytes(
                    KpmState(targetPath, exe, now)), records);
                // KOTOR Patch Manager's backup record, where this install set the 4 GB flag,
                // lists the patches too (WriteKpmBackup).
                string[] backup = records.Rows.Find(r => r[0] == "file" && r[1].IndexOf(KpmBackupInfix,
                    StringComparison.Ordinal) >= 0 && r[1].EndsWith(".json", StringComparison.OrdinalIgnoreCase));
                if (backup != null && OwnedAsWritten(folder, records.Rows, backup[1]))
                {
                    StringBuilder ids = new StringBuilder();
                    foreach (string id in now)
                        ids.Append(ids.Length > 0 ? ", " : "").Append('"').Append(id).Append('"');
                    string json = File.ReadAllText(GamePath.Combine(folder, backup[1]), Encoding.UTF8);
                    json = Regex.Replace(json, "\"InstalledPatches\": \\[[^\\]]*\\]", "\"InstalledPatches\": [" + ids + "]",
                        RegexOptions.CultureInvariant);
                    RewriteOwned(folder, backup[1], new UTF8Encoding(false).GetBytes(json), records);
                }
                bool fpsWas;
                if (!before.TryGetValue("high-fps", out fpsWas) || fpsWas != KmrpSettings.HighFpsFix)
                {
                    SafeProgress(progress, 70, "Updating display settings…");
                    // Over the install as it stands: the backup stays the one from before
                    // KMRP, and only the frame-rate keys change (IniOperations.Configure).
                    int iniWidth = width, iniHeight = height;
                    IniOperations.KeepChosenSize(targetPath, ref iniWidth, ref iniHeight, null);
                    IniEditState ini = IniOperations.Configure(targetPath, iniWidth, iniHeight, true, report);
                    records.Remove(r => r[0] == "ini");
                    records.AddRange(ini.Rows);
                }
                records.Remove(r => r[0] == SettingsRow);
                records.Add(SettingsRecord());
                records.Finish();
            }
            catch (Exception failure)
            {
                throw new IOException(failure.Message + " The settings were not all applied: press Repair to " +
                    "put the install right.", failure);
            }
            SafeProgress(progress, 100, "Settings applied");
            List<string> moves = added.ConvertAll(id => "added " + id);
            moves.AddRange(taken.ConvertAll(id => "removed " + id));
            SafeReport(report, "Applied " + (changed ?? "the settings") + ", without installing again" +
                (moves.Count == 0 ? "." : " (" + String.Join(", ", moves.ToArray()) + ")."));
        }

        // ------------------------------------------------------------ install

        internal static void Install(string targetPath, int width, int height, Action<string> report,
            Action<int, string> progress)
        {
            using (InstallGuard.Take(targetPath))
                InstallTimed(targetPath, width, height, report, progress);
        }

        private static void InstallTimed(string targetPath, int width, int height, Action<string> report,
            Action<int, string> progress)
        {
            if (progress == null)
            {
                InstallCore(targetPath, width, height, report, null, null);
                return;
            }
            // The time left, under the window's button from the start (InstallClock): the
            // files take a few seconds, a few more over an earlier install, which is taken
            // away first; the art takes the rest.
            bool over = false;
            try { over = IsInstalled(Path.GetFullPath(targetPath)); }
            catch { }
            int workers, sizes;
            double secondsPerSize;
            InstallPlatform.ArtPlan(out workers, out sizes, out secondsPerSize);
            InstallClock timing = new InstallClock(progress, over ? 6 : 3, sizes, workers, secondsPerSize);
            try { InstallCore(targetPath, width, height, report, timing.Report, timing); }
            finally { timing.Stop(); }
        }

        private static void InstallCore(string targetPath, int width, int height, Action<string> report,
            Action<int, string> progress, InstallClock timing)
        {
            SafeProgress(progress, 0, "Preparing game files…");
            targetPath = Path.GetFullPath(targetPath);
            if (!File.Exists(targetPath))
                throw new FileNotFoundException("swkotor.exe was not found.", targetPath);
            ResolutionChoice resolution = ResolutionCatalog.Find(width, height);

            // Every check that can refuse comes first, so a refusal changes nothing.
            // The bar: the files in the first fifth, which take a second or two, and the art,
            // which takes the rest of the time (ArtPreparation), from 22% (2026-10-19).
            SafeProgress(progress, 2, "Checking game files…");
            bool standalone = IsStandaloneInstall(targetPath);
            if (standalone && !PatchOperations.CanRestoreStandalone(targetPath))
                throw new InvalidOperationException(
                    "An earlier KMRP, which patched swkotor.exe, is installed, and its backup of " +
                    "the original swkotor.exe or swkotor.ini is missing or damaged, so it cannot " +
                    "be removed. Reinstall the game's original swkotor.exe, then install again.");
            if (!standalone && GameExecutable.Identify(targetPath) == null)
                throw new InvalidDataException("This swkotor.exe is not the Steam, GOG or Editable 1.03 " +
                    "version KMRP supports. No changes were made.");
            // A newer build than this one is never replaced by it: the window then offers
            // only Restore Original, and this refuses for the command line (the
            // maintainer, 2026-10-19).
            int? age = CompareInstalled(targetPath);
            if (age == 1)
                throw new InvalidOperationException("The KMRP installed in this game is a newer build (" +
                    BuildStamp.Display(InstalledBuild(targetPath).Value) + ") than this installer (" +
                    BuildStamp.Display(BuildStamp.Current.Value) + "). No changes were made. To go back to " +
                    "this build, restore the original files first, then install.");
            if (!File.Exists(IniOperations.PathForExecutable(targetPath)))
                throw new FileNotFoundException(
                    "swkotor.ini was not found beside swkotor.exe. Launch the game once or place the INI in the game folder before installing.",
                    IniOperations.PathForExecutable(targetPath));
            RequireReadableManifest(targetPath);
            string foreign = ForeignRuntimeFile(targetPath, standalone);
            // KPM's own files decide, since 2026-09-30 alone: the Advanced Settings
            // option that also chose an install for KPM was removed (MainForm).
            bool engine = foreign == null;
            if (engine)
                RequireBink(targetPath);
            else if (foreign != null)
                SafeReport(report, foreign + " is in the game folder: KOTOR Patch Manager manages this " +
                    "game, so KMRP adds its patch there and leaves the game's files to it.");

            bool upgrading = standalone;
            if (standalone)
            {
                // The standalone installer's own restore puts back the executable it
                // rewrote, from the backup it made, and everything else it installed
                // -- its runtime, K1DC, Override, the INI -- before this install starts.
                SafeProgress(progress, 4, "Removing the earlier KMRP…");
                SafeReport(report, "An earlier KMRP, which patched swkotor.exe, is installed. " +
                    "Restoring the original game files before installing this one.");
                PatchOperations.RestoreStandalone(targetPath, report, null, true);
                if (IsStandaloneInstall(targetPath) || !GoldPatch.IsSupportedSourceFile(targetPath))
                    throw new InvalidDataException("The earlier KMRP could not be removed, so nothing of this one was installed.");
            }
            // KMRP's own files go into its folder from here on, an earlier install's with
            // them (KmrpFolder, since 2026-10-20). After the standalone restore, which removes
            // its files where it wrote them: moved first, its licence stayed in KMRP's folder
            // and this install then refused it (2026-11-01, Test-ReinstallOverOlderBuild).
            KmrpFolder.Migrate(targetPath, report);
            if (IsInstalled(targetPath))
            {
                upgrading = true;
                // Everything the earlier install put here goes, and only what the
                // settings choose now is installed: a patch turned off since is removed,
                // one turned on is added (the maintainer, 2026-10-19; Test-InstallerPatch
                // Case 7).
                DateTimeOffset? installed = InstalledBuild(targetPath);
                SafeReport(report, age == 0 ? "Reinstalling this build, with the settings chosen now." :
                    installed.HasValue && BuildStamp.Current.HasValue
                        ? "Upgrading KMRP from the build of " + BuildStamp.Display(installed.Value) + " to the build of " +
                          BuildStamp.Display(BuildStamp.Current.Value) + ", with the settings chosen now."
                        : "Replacing the installed KMRP files, with the settings chosen now.");
                // Installing for KPM: a runtime KPM took over stays KPM's, even with
                // only KMRP's patches in it, since this install puts nothing in its place.
                Restore(targetPath, report, null, !engine, true);
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
            if (upgrading)
                IniOperations.KeepChosenSize(targetPath, ref width, ref height, report);
            InstallJournal records = new InstallJournal(targetPath, width, height);
            IniEditState iniState = null;
            object dpiState = null;
            string kpatchFolder = null;
            try
            {
                SafeProgress(progress, 6, "Updating display settings…");
                dpiState = InstallPlatform.InstallDpi(targetPath, report);
                // NVIDIA's present method is the player's (2026-10-30): the module draws each
                // frame offscreen and shows it finished (K1OffscreenFrame.cpp), so the layered
                // path no longer flashes, and Windows Auto HDR and RTX HDR need that path
                // (issue 73). Until then KMRP set Prefer native wherever the game would
                // inherit layered; a value it set that way, with its record, is removed here.
                InstallPlatform.RemoveOldNvidiaSetting(targetPath, report);
                iniState = IniOperations.Configure(targetPath, width, height, upgrading, report);
                records.AddRange(iniState.Rows);

                SafeProgress(progress, 10, engine ? "Installing KMRP's patch…" : "Preparing the patch for KPM…");
                // The controller's settings are the player's to edit: written only when
                // absent, and claimed only then, as the standalone installer does.
                string settings = GamePath.Combine(folder, KmrpFolder.ControllerSettings);
                if (!File.Exists(settings))
                    WriteOwned(folder, KmrpFolder.ControllerSettings,
                        new UTF8Encoding(false).GetBytes(ControllerOperations.DefaultSettings), records);
                // An older KMRP's standalone K1DC (dinput8.dll and the .asi) out first: K1DC
                // is one of the patches now, and both at once would change the same places.
                InstallPlatform.RestoreDriverCompat(targetPath, report);
                if (engine)
                {
                    List<string> patches = ChosenPatches(folder, report);
                    InstallEngine(folder, Path.GetFileName(targetPath), exe, patches, records, report);
                    SafeProgress(progress, 16, "Setting the 4 GB flag…");
                    if (!steam)
                        SetLargeAddressAware(targetPath, exe, patches, records, report);
                    // Windows 7 and 8, where K1DC's .kpatch cannot run: its author's build
                    // for them, beside the game (DriverCompatStandalone, InstallCore.cs).
                    if (!patches.Contains(DriverCompatPatchId) && DriverCompatRoute(folder, null) == DriverCompatWindows7)
                        DriverCompatStandalone.Install(targetPath, report);
                }
                SafeProgress(progress, 18, "Adding the patch to KPM…");
                kpatchFolder = DeliverKpatches(folder, !engine, records, report);
                SafeProgress(progress, 20, "Adding KMRP's art…");
                Directory.CreateDirectory(GamePath.Combine(folder, PatchFolder));
                WriteOwnedResource(folder, PatchFolder + "\\" + PackName, PackResource, records);
                records.Add(SettingsRecord());
                records.Finish();
            }
            catch (Exception failure)
            {
                string left = RollBack(targetPath, records.Rows, iniState, dpiState);
                throw new IOException(failure.Message + " " + (left ??
                    (upgrading ? "The earlier KMRP had already been removed; what this install changed was undone."
                               : "What this install changed was undone.")), failure);
            }
            // Every size the display offers made now, from the pack just written, so the
            // game starts and changes size without waiting (the maintainer, 2026-10-19:
            // "smoother user experience comes priority"). Not part of the install: a size
            // not made here, the game makes when it first needs it.
            InstallPlatform.PrepareArt(folder, KpatchResource, KpatchModuleEntry, report, progress, timing, 22, 99);
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
                    SafeReport(report, "KMRP's patch" + (KmrpSettings.ControllerSupport ? " and the controller patch are" : " is") +
                        " also in KOTOR Patch Manager's patch " +
                        "folder (" + kpatchFolder + "), so KPM lists them if you add other patches there.");
                return;
            }
            SafeReport(report, "KMRP's patch is ready in KOTOR Patch Manager. swkotor.exe was not modified.");
            bool inGameFolder = String.Equals(kpatchFolder, GamePath.Combine(folder, KpatchFolderName),
                StringComparison.OrdinalIgnoreCase);
            SafeReport(report, (inGameFolder
                ? "KMRP's patch, KMRP.kpatch" + (KmrpSettings.ControllerSupport
                      ? ", and the controller patch, KOTOR 1 Native Controller Mod + Xbox HUD.kpatch, are in "
                      : ", is in ") + kpatchFolder + ". Copy to KOTOR Patch " +
                  "Manager's patch folder (or choose this folder in KPM), then open KPM"
                : "KMRP's patch, KMRP.kpatch" + (KmrpSettings.ControllerSupport
                      ? ", and the controller patch, KOTOR 1 Native Controller Mod + Xbox HUD.kpatch, are in "
                      : ", is in ") + "KOTOR Patch Manager's patch folder (" + kpatchFolder + "). Now open KPM") +
                " and tick KMRP" + (KmrpSettings.ControllerSupport ? " and the controller patch" : "") +
                ". KMRP includes map notes, the " +
                "movie fixes and the 4 GB, texture, grass and save-game memory fixes, so leave " +
                "KPM's own ones unticked. Press Apply, and start the game with Launch.");
            if (steam)
                SafeReport(report, "Steam: in KOTOR Patch Manager choose the proxy deployment, " +
                    "and start the game from Steam. Steam's swkotor.exe cannot take the 4 GB flag.");
        }

        /// <summary>Takes a failed install out again. Each step is tried whatever became of
        /// the one before it; until 2026-11-01 a file that would not delete ended the
        /// rollback there, with the game's binkw32.dll still renamed, and the window said
        /// nothing incomplete was left behind (audit INS-04). The manifest goes last and only
        /// when every step worked, since it is what lets Restore Original finish the job.
        /// Returns null, or what the player has to do next.</summary>
        private static string RollBack(string targetPath, List<string[]> records, IniEditState iniState, object dpiState)
        {
            string folder = FolderOf(targetPath);
            string first = null;
            Action<Action> step = delegate(Action undo)
            {
                try { undo(); }
                catch (Exception error) { first = first ?? error.Message; }
            };
            step(() => InstallPlatform.RestoreDriverCompat(targetPath, null));
            step(() => RemoveKpatches(records, null));
            step(() => RemoveOwned(folder, records, null));
            step(() => RemoveInProgress(folder));
            step(() => RemovePatchOptions(folder, records));
            step(() => UndoEngineChanges(targetPath, records, null));
            step(() => IniOperations.Rollback(iniState));
            step(() => InstallPlatform.RollbackDpi(dpiState));
            if (first == null)
                step(() => FileGuard.Delete(ManifestPath(targetPath)));
            return first == null ? null : "Not everything this install changed could be undone (" + first +
                "). Close KOTOR and anything using its files, then press Restore Original to finish.";
        }

        /// <summary>Removes what Install recorded, of either kind: the manifest says
        /// what was installed. An install by the standalone installer is its own
        /// restore's.</summary>
        internal static void Restore(string targetPath, Action<string> report, Action<int, string> progress)
        {
            using (InstallGuard.Take(targetPath))
                Restore(targetPath, report, progress, false, false);
        }

        /// <summary>`keepCache`: an install over this one is about to make the art again,
        /// and finds what is already made for its build (Install).</summary>
        private static void Restore(string targetPath, Action<string> report, Action<int, string> progress,
            bool keepKpmRuntime, bool keepCache)
        {
            SafeProgress(progress, 0, "Preparing to restore…");
            targetPath = Path.GetFullPath(targetPath);
            if (!IsInstalled(targetPath) && IsStandaloneInstall(targetPath))
            {
                PatchOperations.RestoreStandalone(targetPath, report, progress);
                return;
            }
            RequireReadableManifest(targetPath);
            KmrpFolder.Migrate(targetPath, report);
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
            InstallPlatform.RestoreDriverCompat(targetPath, report);
            RemoveKpatches(records, report);
            if (whole)
                RemoveKpmRuntime(targetPath, untouched, records, report);
            RemoveOwned(folder, records, report);
            RemoveInProgress(folder);
            RemovePatchOptions(folder, records);
            UndoEngineChanges(targetPath, records, report);
            // From here a record of KMRP's that cannot be used stops only its own step, and
            // the player is told at the end. It stopped the whole restore until 2026-11-01,
            // with KMRP half removed and the same refusal every time after (audit INS-05);
            // and what was not put back was reported as restored (audit INS-08). The proxy
            // has gone by now even when the game's own binkw32.dll cannot come back: left
            // in place, the next install would take it for the game's and move it aside.
            List<string> notRestored = new List<string>();
            if (engine && !File.Exists(GamePath.Combine(folder, BinkName)))
                notRestored.Add(BinkName + ", which was missing or had changed");
            Action<string, Action> attempt = delegate(string what, Action restore)
            {
                try { restore(); }
                catch (InvalidDataException error) { notRestored.Add(what + " (" + error.Message + ")"); }
            };
            attempt("the high-DPI setting", () => InstallPlatform.RestoreDpi(targetPath, report));
            attempt("the NVIDIA setting", () => InstallPlatform.RemoveOldNvidiaSetting(targetPath, report));
            SafeProgress(progress, 92, "Restoring display settings…");
            // An install over this one leaves swkotor.ini as the player has it: the whole
            // backup going back here lost every setting changed since the first install,
            // KMRP's own Text, Icon and HUD sizes with them (2026-11-01, audit INS-01).
            if (!keepCache)
                attempt("swkotor.ini", delegate
                {
                    if (!IniOperations.Restore(targetPath, records.FindAll(r => r[0] == "ini"), report))
                        notRestored.Add("swkotor.ini, as its backup is missing");
                });
            FileGuard.Delete(ManifestPath(targetPath));
            // An install over this one (keepCache) writes into KMRP's folders next.
            if (!keepCache)
                KmrpFolder.RemoveEmpty(targetPath);
            if (!keepCache)
                InstallPlatform.RemoveArtCache(report);
            SafeProgress(progress, 100, "Restore complete");
            if (notRestored.Count > 0)
            {
                string left = "KMRP was removed, but this could not be put back: " +
                    String.Join("; ", notRestored.ToArray()) + ". " + (IsSteam(targetPath)
                        ? "Steam's Verify integrity (Properties, Installed Files) replaces a game file."
                        : "Reinstalling the game replaces a game file.");
                if (keepCache)
                    SafeReport(report, left);
                else
                    throw new IOException(left);
            }
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
                // A module or the art pack in patches\ changed alone is not KPM's Apply,
                // which rewrites the runtime, its config or its state; it re-extracts the
                // modules byte for byte. Counted until 2026-10-27, when a module swapped
                // in by hand for a test made a restore leave the whole runtime behind.
                if (record[1].StartsWith(PatchFolder + "\\", StringComparison.OrdinalIgnoreCase))
                    continue;
                string path = GamePath.Combine(folder, record[1]);
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
                string config = GamePath.Combine(folder, ConfigName);
                if (!File.Exists(config))
                    return false;
                List<string> ids = new List<string>();
                foreach (Match match in Regex.Matches(File.ReadAllText(config, Encoding.UTF8),
                             "^\\s*id\\s*=\\s*\"([^\"]*)\"\\s*$", RegexOptions.Multiline | RegexOptions.CultureInvariant))
                    ids.Add(match.Groups[1].Value);
                string state = GamePath.Combine(folder, KpmStateName);
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
                string patches = GamePath.Combine(folder, PatchFolder);
                if (Directory.Exists(patches))
                {
                    if (Directory.GetDirectories(patches).Length > 0)
                        return false;
                    // KMRP's art pack is KMRP's too (beside its module since 2026-10-19).
                    // Until 2026-10-27 only modules counted here, so with the pack there this
                    // was never true, and a restore that found the runtime taken over left
                    // all of it behind, the pack included, for an install KMRP then refused
                    // to write over ("Left the existing patches\kmrp-assets.pack alone").
                    foreach (string module in Directory.GetFiles(patches))
                        if (!String.Equals(Path.GetFileName(module), PackName, StringComparison.OrdinalIgnoreCase) &&
                            (!String.Equals(Path.GetExtension(module), ".dll", StringComparison.OrdinalIgnoreCase) ||
                             Array.IndexOf(EnginePatches, Path.GetFileNameWithoutExtension(module).ToLowerInvariant()) < 0))
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
                FileGuard.Delete(GamePath.Combine(folder, name));
            foreach (string id in EnginePatches)
                FileGuard.Delete(GamePath.Combine(folder, PatchFolder, id + ".dll"));
            string[] rename = records.Find(r => r[0] == "moved" && r.Length == 4);
            string moved = GamePath.Combine(folder, BinkMovedName);
            if (rename != null && File.Exists(moved) && GoldPatch.HashFile(moved) == rename[3])
                FileGuard.Delete(GamePath.Combine(folder, BinkName));
            SafeReport(report, "Removed KOTOR Patch Manager's runtime and put back the untouched swkotor.exe.");
        }

        /// <summary>A record of KOTOR Patch Manager's runtime as this install laid it out:
        /// the runtime, its config, its identity file and the backup it restores from,
        /// the modules, the proxy and the rename, and the 4 GB flag KPM's own KMRP patch
        /// sets too. Not the art pack in patches\: nothing of KPM's reads or writes it, so
        /// it stays KMRP's to remove. Counted as runtime until 2026-11-01, when a takeover
        /// left it behind unrecorded and every later install refused to write over it
        /// (audit INS-02, Test-InstallerPatch Case 13).</summary>
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
                (name.StartsWith(PatchFolder + "\\", StringComparison.OrdinalIgnoreCase) &&
                 !String.Equals(name, PatchFolder + "\\" + PackName, StringComparison.OrdinalIgnoreCase));
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
                string path = GamePath.Combine(folder, name);
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
                File.Exists(GamePath.Combine(folder, BinkName)))
                return;
            throw new FileNotFoundException("binkw32.dll was not found beside swkotor.exe. KMRP loads " +
                "through it; restore the game's own binkw32.dll (in Steam: Properties, Installed " +
                "Files, Verify integrity) and try again.", GamePath.Combine(folder, BinkName));
        }

        /// <summary>The patches this install puts in: KMRP's, the controller patch
        /// unless Controller Support is off, High FPS Fixes while High FPS Fix is on,
        /// Marked Empty Containers while that is on, and K1 Modern Driver Compatibility
        /// while that is on (DriverCompatChosen). KMRP's options are chosen separately
        /// (PatchOptions).</summary>
        private static List<string> ChosenPatches(string folder, Action<string> report)
        {
            List<string> patches = new List<string> { PatchId };
            if (KmrpSettings.ControllerSupport)
                patches.Add(ControllerPatchId);
            if (KmrpSettings.HighFpsFix)
                patches.Add(HighFpsPatchId);
            if (KmrpSettings.MarkedEmptyContainers)
                patches.Add(EmptyContainersPatchId);
            if (DriverCompatRoute(folder, report) == DriverCompatKpatch)
                patches.Add(DriverCompatPatchId);
            return patches;
        }

        // How K1 Modern Driver Compatibility goes in (DriverCompatRoute).
        private const int DriverCompatNone = 0, DriverCompatKpatch = 1, DriverCompatWindows7 = 2;

        /// <summary>How K1 Modern Driver Compatibility goes in, with the option on: as its
        /// .kpatch where the PC has every function that module imports, and as its author's
        /// standalone build for Windows 7 and 8 where it does not
        /// (DriverCompatStandalone.Install); not at all with a standalone copy of the
        /// player's own beside the game, which would change the same places, and that is
        /// said.</summary>
        private static int DriverCompatRoute(string folder, Action<string> report)
        {
            if (!KmrpSettings.DriverCompatibility)
                return DriverCompatNone;
            // An older KMRP's standalone copy is gone by now (InstallPlatform.RestoreDriverCompat).
            if (File.Exists(GamePath.Combine(folder, StandaloneDriverCompatName)))
            {
                SafeReport(report, "Left the existing " + StandaloneDriverCompatName + " alone and did not " +
                    "install KMRP's copy of Modern Driver Compatibility: the two would change the same places.");
                return DriverCompatNone;
            }
            return InstallPlatform.DriverCompatMissing() == null ? DriverCompatKpatch : DriverCompatWindows7;
        }


        /// <summary>The patch's options as Advanced Settings has them, in the order its
        /// manifest declares them: id and value. The movie fixes are not among them:
        /// they are part of KMRP, as when they were a patch the installer always chose.</summary>
        internal static KeyValuePair<string, bool>[] PatchOptions()
        {
            return new[]
            {
                new KeyValuePair<string, bool>("map-notes", KmrpSettings.MarkerFixes),
                new KeyValuePair<string, bool>("hd-icons", KmrpSettings.HdIcons),
                new KeyValuePair<string, bool>("debug-logs", KmrpSettings.DebugLogs),
            };
        }

        /// <summary>The controller patch's options as this installer sets them: only
        /// debug logs. Its Xbox-style HUD option is left out on purpose: the module takes
        /// a missing value as "use Style under [Hud] in KMRP\controller.ini", the
        /// player's own setting, and a 0 written here would override it.</summary>
        internal static KeyValuePair<string, bool>[] ControllerPatchOptions()
        {
            return new[] { new KeyValuePair<string, bool>("debug-logs", KmrpSettings.DebugLogs) };
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
            return PatchConfigSection(PatchId, "Kmrp.engine.hooks", options);
        }

        /// <summary>The same for either patch: its id, and the resource its hooks are
        /// under (Kpatches).</summary>
        internal static string PatchConfigSection(string id, string hooksResource, KeyValuePair<string, bool>[] options)
        {
            return PatchConfigSection(id, hooksResource, options, true);
        }

        /// <summary>The same, for a patch with or without a module: one without names no
        /// DLL (`dll = ""`), as KPM's PatchApplicator writes it, and KPM's runtime then
        /// loads nothing for it (Marked Empty Containers, whose one hook is a replace
        /// hook).</summary>
        internal static string PatchConfigSection(string id, string hooksResource, KeyValuePair<string, bool>[] options,
                                                  bool hasModule)
        {
            StringBuilder section = new StringBuilder();
            section.Append("[[patches]]\nid = \"").Append(id).Append("\"\ndll = \"");
            if (hasModule)
                section.Append(PatchFolder).Append('/').Append(id).Append(".dll");
            section.Append("\"\n");
            section.Append(Encoding.UTF8.GetString(ReadResource(hooksResource)));
            foreach (KeyValuePair<string, bool> option in options)
            {
                if (!option.Value)
                    continue;
                byte[] hooks = TryReadResource(hooksResource + "." + option.Key);
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
        internal const string ControllerOptionsName = OptionsFolder + "\\" + ControllerPatchId + ".ini";
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
        private static void WritePatchOptions(string folder, string name, KeyValuePair<string, bool>[] options,
            InstallJournal records)
        {
            string path = GamePath.Combine(folder, name);
            string rest = File.Exists(path) ? WithoutOptionsSection(File.ReadAllText(path, OptionsEncoding)) : "";
            StringBuilder text = new StringBuilder();
            text.Append('[').Append(OptionsSection).Append("]\r\n");
            foreach (KeyValuePair<string, bool> option in options)
                text.Append(option.Key).Append('=').Append(option.Value ? '1' : '0').Append("\r\n");
            if (rest.Length > 0)
                text.Append("\r\n").Append(rest);
            Directory.CreateDirectory(GamePath.Combine(folder, OptionsFolder));
            WriteWhole(path, OptionsEncoding.GetBytes(text.ToString()), hash => records.Add(new[] { "options", name }));
        }

        /// <summary>Takes the section out again. A file that held nothing else is
        /// deleted, and the folder once it is empty; anything else in them stays.</summary>
        private static void RemovePatchOptions(string folder, List<string[]> records)
        {
            if (!records.Exists(r => r[0] == "options"))
                return;
            try
            {
                foreach (string[] record in records)
                {
                    if (record[0] != "options")
                        continue;
                    string path = GamePath.Combine(folder, record[1]);
                    if (!File.Exists(path))
                        continue;
                    string text = File.ReadAllText(path, OptionsEncoding);
                    string rest = WithoutOptionsSection(text);
                    if (rest.Trim().Length == 0)
                        File.Delete(path);
                    else if (rest.Length != text.Length)
                        File.WriteAllText(path, rest, OptionsEncoding);
                }
                string directory = GamePath.Combine(folder, OptionsFolder);
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
            InstallJournal records, Action<string> report)
        {
            WriteOwned(folder, RuntimeName, ReadResource("Kmrp.engine.runtime"), records);
            WriteOwned(folder, KpmLicenseName, ReadResource("Kmrp.engine.license"), records);
            KeyValuePair<string, bool>[] options = PatchOptions();
            KeyValuePair<string, bool>[] controllerOptions = ControllerPatchOptions();
            Directory.CreateDirectory(GamePath.Combine(folder, PatchFolder));
            bool controller = patches.Contains(ControllerPatchId);
            bool highFps = patches.Contains(HighFpsPatchId);
            bool emptyContainers = patches.Contains(EmptyContainersPatchId);
            bool driverCompat = patches.Contains(DriverCompatPatchId);
            for (int i = 0; i < Kpatches.GetLength(0); i++)
            {
                if (!patches.Contains(Kpatches[i, 1]))
                    continue;
                // A patch without a module (Marked Empty Containers, the only one allowed
                // to have none) puts nothing in patches\.
                byte[] module = PatchModule(Kpatches[i, 2], Kpatches[i, 1] != EmptyContainersPatchId);
                if (module != null)
                    WriteOwned(folder, PatchFolder + "\\" + Kpatches[i, 1] + ".dll", module, records);
            }
            WriteOwned(folder, ConfigName, new UTF8Encoding(false).GetBytes(PatchConfig(exe, patches)), records);
            WritePatchOptions(folder, OptionsName, options, records);
            if (controller)
                WritePatchOptions(folder, ControllerOptionsName, controllerOptions, records);
            WriteOwned(folder, KpmStateName, new UTF8Encoding(false).GetBytes(
                KpmState(GamePath.Combine(folder, exeName), exe, patches)), records);

            // The proxy last, since it is what makes the game load the rest.
            string bink = GamePath.Combine(folder, BinkName);
            string moved = GamePath.Combine(folder, BinkMovedName);
            string binkHash = GoldPatch.HashFile(bink);
            records.Add(new[] { "moved", BinkName, BinkMovedName, binkHash });
            File.Move(bink, moved);
            WriteOwned(folder, BinkName, ReadResource("Kmrp.engine.proxy"), records);
            List<string> off = new List<string>();
            foreach (KeyValuePair<string, bool> option in options)
                if (!option.Value && option.Key != "debug-logs")
                    off.Add(option.Key);
            SafeReport(report, "Installed KOTOR Patch Manager's runtime with KMRP's patch" +
                (controller ? " and the controller patch" : ", without controller support") +
                (highFps ? ", and D3M0's High FPS Fixes" : "") +
                (emptyContainers ? ", and ShaeMyName's Marked Empty Containers" : "") +
                (driverCompat ? ", and Synchro's K1 Modern Driver Compatibility " + DriverCompatVersion : "") +
                (off.Count == 0 ? ", every option on." : ", without: " + String.Join(", ", off.ToArray()) + "."));
        }

        /// <summary>patch_config.toml for `patches`, with the options Advanced Settings has
        /// now. KMRP's first: the controller patch's module looks for kmrp.dll when it
        /// starts, and KOTOR Patch Manager loads the modules in this order (Kpatches). Used
        /// by Install and by ApplySettings, so both write the same file.</summary>
        private static string PatchConfig(GameExecutable exe, List<string> patches)
        {
            KeyValuePair<string, bool>[] options = PatchOptions();
            KeyValuePair<string, bool>[] controllerOptions = ControllerPatchOptions();
            // The bundled patches of others have no options.
            KeyValuePair<string, bool>[] none = new KeyValuePair<string, bool>[0];
            StringBuilder config = new StringBuilder("target_version_sha = \"" + exe.Hash + "\"\n");
            for (int i = 0; i < Kpatches.GetLength(0); i++)
            {
                if (!patches.Contains(Kpatches[i, 1]))
                    continue;
                bool hasModule = Kpatches[i, 1] != EmptyContainersPatchId || PatchModule(Kpatches[i, 2], false) != null;
                config.Append('\n').Append(PatchConfigSection(Kpatches[i, 1], Kpatches[i, 3],
                    Kpatches[i, 1] == PatchId ? options : Kpatches[i, 1] == ControllerPatchId ? controllerOptions : none,
                    hasModule));
            }
            return config.ToString();
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
        /// of the unmodified file for KOTOR Patch Manager (WriteKpmBackup). The flag already
        /// set, by the player or another tool, is left alone and not recorded, so restore
        /// leaves it too.</summary>
        private static void SetLargeAddressAware(string targetPath, GameExecutable exe, List<string> patches,
            InstallJournal records, Action<string> report)
        {
            string hash = GoldPatch.HashFile(targetPath);
            if (hash == exe.LargeAddressAwareHash)
            {
                SafeReport(report, "swkotor.exe already has the 4 GB flag.");
                return;
            }
            if (hash != exe.Hash || exe.LargeAddressAwareHash == null)
                throw new InvalidDataException("swkotor.exe changed during the install. No changes were kept.");
            WriteKpmBackup(targetPath, exe, patches, records);
            records.Add(new[] { "laa", "set" });
            WriteCharacteristics(targetPath, PeCompatibility.LargeAddressAwareCharacteristics);
            if (GoldPatch.HashFile(targetPath) != exe.LargeAddressAwareHash)
            {
                WriteCharacteristics(targetPath, PeCompatibility.OriginalCharacteristics);
                throw new IOException("Setting the 4 GB flag on swkotor.exe could not be verified. No changes were kept.");
            }
            SafeReport(report, "Set the 4 GB flag on swkotor.exe (one bit of its header).");
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
            InstallJournal records)
        {
            string folder = FolderOf(targetPath);
            string name = Path.GetFileName(targetPath) + KpmBackupInfix +
                DateTime.Now.ToString("yyyyMMdd_HHmmss", CultureInfo.InvariantCulture);
            WriteOwned(folder, name, File.ReadAllBytes(targetPath), records);
            if (records.Rows[records.Rows.Count - 1][2] != exe.Hash)
                throw new InvalidDataException("swkotor.exe changed during the install. No changes were kept.");
            StringBuilder ids = new StringBuilder();
            foreach (string id in patches)
                ids.Append(ids.Length > 0 ? ", " : "").Append('"').Append(id).Append('"');
            string json = "{\r\n" +
                "  \"OriginalPath\": \"" + JsonString(targetPath) + "\",\r\n" +
                "  \"BackupPath\": \"" + JsonString(GamePath.Combine(folder, name)) + "\",\r\n" +
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
            return FileGuard.InUseMessage(path);
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
                string original = GamePath.Combine(folder, record[1]);
                string moved = GamePath.Combine(folder, record[2]);
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
            string patches = GamePath.Combine(folder, PatchFolder);
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
                else if (exe == null || hash != exe.Hash)
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

        /// <summary>The patch's module, out of the embedded .kpatch: the installer carries
        /// it once, not twice. (Stored uncompressed while it held the art, 189 MB at most;
        /// deflated since 2026-10-19, when the art became the pack and the module 0.7 MB.)
        /// Null for a patch without a module where `required` is false (Marked Empty
        /// Containers); the .kpatch itself must be in this build either way.</summary>
        private static byte[] PatchModule(string resource, bool required)
        {
            using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(resource))
            {
                if (stream == null)
                    throw new InvalidDataException("This build does not carry " + resource + ".");
                using (ZipArchive zip = new ZipArchive(stream, ZipArchiveMode.Read, false))
                {
                    ZipArchiveEntry entry = zip.GetEntry(KpatchModuleEntry);
                    if (entry == null && !required)
                        return null;
                    if (entry == null)
                        throw new InvalidDataException(resource + " carries no module.");
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
        //   incomplete                       the install had not finished when this was
        //                                    written (InstallJournal)
        // KMRP for KPM builds before 2026-09-29 wrote file rows only, the same way.

        /// <summary>The rows of an install in progress. They are in the manifest before the
        /// change each one names, the first of them before anything changes, with an
        /// "incomplete" row until Finish: an install stopped at any point (killed, the
        /// power, the window closed) is an install Restore Original or the next install
        /// can take out. Until 2026-11-01 the manifest was written last, so a stopped
        /// install left a runtime nothing recorded, and possibly binkw32.dll renamed,
        /// which the next run took for KOTOR Patch Manager's (audit INS-03). The Mac's
        /// installer records first too (kmrp-mac.sh).</summary>
        private sealed class InstallJournal
        {
            private readonly string executable;
            private readonly int width, height;
            internal readonly List<string[]> Rows = new List<string[]>();

            internal InstallJournal(string executable, int width, int height)
                : this(executable, width, height, new List<string[]>())
            {
            }

            /// <summary>An install changed in place (ApplySettings): its rows to start
            /// from, marked incomplete until Finish, as a new install's are.</summary>
            internal InstallJournal(string executable, int width, int height, List<string[]> rows)
            {
                this.executable = executable;
                this.width = width;
                this.height = height;
                Rows.AddRange(rows);
                WriteManifest(executable, width, height, Rows, false);
            }

            internal void Remove(Predicate<string[]> match)
            {
                if (Rows.RemoveAll(match) > 0)
                    WriteManifest(executable, width, height, Rows, false);
            }

            internal void Add(string[] row)
            {
                Rows.Add(row);
                WriteManifest(executable, width, height, Rows, false);
            }

            internal void AddRange(List<string[]> rows)
            {
                Rows.AddRange(rows);
                WriteManifest(executable, width, height, Rows, false);
            }

            internal void Finish()
            {
                WriteManifest(executable, width, height, Rows, true);
            }
        }

        // Beside the file it will become (WriteWhole).
        private const string InProgressSuffix = ".kmrp-new";

        /// <summary>PATH as a whole file or not at all: written beside it, its length checked,
        /// `recorded` told its hash, and only then moved into place, so a full disk or a
        /// stopped install never leaves part of a file under a name Install owns. Partial
        /// files were left until 2026-11-01, and refused by the next install (audit INS-04).
        /// </summary>
        private static void WriteWhole(string path, long length, Action<string> write, Action<string> recorded)
        {
            string temporary = path + InProgressSuffix;
            try
            {
                write(temporary);
                if (new FileInfo(temporary).Length != length)
                    throw new IOException(Path.GetFileName(path) + " could not be written in full.");
                recorded(GoldPatch.HashFile(temporary));
                FileGuard.MoveOver(temporary, path);
            }
            finally
            {
                FileGuard.Discard(temporary);
            }
        }

        private static void WriteWhole(string path, byte[] data, Action<string> recorded)
        {
            WriteWhole(path, data.Length, temporary => File.WriteAllBytes(temporary, data), recorded);
        }

        /// <summary>What a stopped WriteWhole or swkotor.ini write can leave.</summary>
        private static void RemoveInProgress(string folder)
        {
            foreach (string place in new[] { folder, GamePath.Combine(folder, PatchFolder),
                                             GamePath.Combine(folder, OptionsFolder), GamePath.Combine(folder, KmrpFolder.Name) })
                if (Directory.Exists(place))
                    foreach (string path in Directory.GetFiles(place, "*" + InProgressSuffix))
                        FileGuard.Discard(path);
            foreach (string place in new[] { folder, GamePath.Combine(folder, Path.GetDirectoryName(KmrpFolder.IniBackup)) })
                if (Directory.Exists(place))
                    foreach (string path in Directory.GetFiles(place, "swkotor.ini*.tmp"))
                        FileGuard.Discard(path);
        }

        // Never clobber a file this installer did not write.
        private static void RefuseUnowned(string folder, string name, InstallJournal records)
        {
            if (File.Exists(GamePath.Combine(folder, name)) && !records.Rows.Exists(r => r[0] == "file" &&
                    String.Equals(r[1], name, StringComparison.OrdinalIgnoreCase)))
                throw new IOException("Left the existing " + name + " alone; " +
                    "KMRP was not installed. Move it aside and try again.");
        }

        private static void WriteOwned(string folder, string name, byte[] data, InstallJournal records)
        {
            RefuseUnowned(folder, name, records);
            WriteWhole(GamePath.Combine(folder, name), data, hash => records.Add(new[] { "file", name, hash }));
        }

        /// <summary>WriteOwned for an embedded resource, streamed into the file rather than
        /// held in memory first: the art pack is some 56 MB.</summary>
        private static void WriteOwnedResource(string folder, string name, string resource, InstallJournal records)
        {
            RefuseUnowned(folder, name, records);
            using (Stream source = Assembly.GetExecutingAssembly().GetManifestResourceStream(resource))
            {
                if (source == null)
                    throw new InvalidDataException("This build does not carry " + resource + ".");
                WriteWhole(GamePath.Combine(folder, name), source.Length, delegate(string temporary)
                {
                    using (FileStream output = new FileStream(temporary, FileMode.Create, FileAccess.Write, FileShare.None))
                        source.CopyTo(output);
                }, hash => records.Add(new[] { "file", name, hash }));
            }
        }

        private static bool IsOwnedName(string name)
        {
            if (String.IsNullOrEmpty(name) || name.IndexOf('/') >= 0 || name.IndexOf(':') >= 0)
                return false;
            string[] parts = name.Split('\\');
            // A file in the game folder, in patches\, or in KMRP's own folder (since
            // 2026-10-20: the controller's settings and KPM's licence, KmrpFolder).
            if (parts.Length == 2 && parts[0] != PatchFolder && parts[0] != KmrpFolder.Name)
                return false;
            if (parts.Length > 2)
                return false;
            string leaf = parts[parts.Length - 1];
            return leaf.Length > 0 && leaf != "." && leaf != ".." && leaf.IndexOfAny(Path.GetInvalidFileNameChars()) < 0;
        }

        /// <summary>One file that will not go does not keep the rest here; the first such
        /// file's message is thrown once they have been tried.</summary>
        private static void RemoveOwned(string folder, List<string[]> records, Action<string> report)
        {
            int kept = 0;
            IOException blocked = null;
            foreach (string[] record in records)
            {
                if (record[0] != "file")
                    continue;
                string target = GamePath.Combine(folder, record[1]);
                try
                {
                    if (!File.Exists(target))
                        continue;
                    if (GoldPatch.HashFile(target) != record[2])
                    {
                        kept++;
                        continue;
                    }
                    FileGuard.Delete(target);
                }
                catch (IOException error)
                {
                    blocked = blocked ?? new IOException(FileGuard.InUseMessage(target, "removed"), error);
                }
                catch (UnauthorizedAccessException error)
                {
                    blocked = blocked ?? new IOException(FileGuard.InUseMessage(target, "removed"), error);
                }
            }
            if (kept > 0)
                SafeReport(report, "Left " + kept.ToString(CultureInfo.InvariantCulture) +
                    " file(s) in place because they changed after install.");
            if (blocked != null)
                throw blocked;
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
        private static string DeliverKpatches(string gameFolder, bool forPatchManager, InstallJournal records,
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
            string folder = GamePath.Combine(gameFolder, KpatchFolderName);
            Directory.CreateDirectory(folder);
            WriteKpatches(folder, true, records, report);
            return folder;
        }

        private static void WriteKpatches(string folder, bool withReadme, InstallJournal records, Action<string> report)
        {
            for (int i = 0; i < Kpatches.GetLength(0); i++)
            {
                // The controller patch's file only with Controller Support on, the High
                // FPS Fixes patch's only with High FPS Fix on, and Marked Empty
                // Containers' only with that on.
                if (Kpatches[i, 1] == ControllerPatchId && !KmrpSettings.ControllerSupport)
                    continue;
                if (Kpatches[i, 1] == HighFpsPatchId && !KmrpSettings.HighFpsFix)
                    continue;
                if (Kpatches[i, 1] == EmptyContainersPatchId && !KmrpSettings.MarkedEmptyContainers)
                    continue;
                // K1DC's only with Modern Driver Compatibility on. Not asked of this PC: the
                // file is for KOTOR Patch Manager, which checks the game itself.
                if (Kpatches[i, 1] == DriverCompatPatchId && !KmrpSettings.DriverCompatibility)
                    continue;
                // A copy of KMRP's own patches is brought up to this version. The other
                // three are their authors': a file of that name already in the folder is
                // the player's and is left as it is (no id to match).
                bool theirs = Kpatches[i, 1] == HighFpsPatchId || Kpatches[i, 1] == EmptyContainersPatchId ||
                              Kpatches[i, 1] == DriverCompatPatchId;
                WriteKpatch(GamePath.Combine(folder, Kpatches[i, 0]), ReadResource(Kpatches[i, 2]),
                    theirs ? null : Kpatches[i, 1], records, report);
            }
            if (!withReadme)
                return;
            WriteKpatch(GamePath.Combine(folder, KpatchReadmeName), ReadResource("Kmrp.kpatch.readme"), null, records, report);
            WriteKpatch(GamePath.Combine(folder, KpatchLicenseName), ReadResource("Kmrp.engine.license"), null, records, report);
        }

        /// <summary>One file of the set, recorded "created" when it was not there, which
        /// restore removes while it is as written, or "replaced" when it was, which restore
        /// leaves: an older copy of the same KMRP patch (its manifest's id, `patchId`) is
        /// brought up to this version, since KMRP's module refuses another version's data
        /// file, but a file the player had is never deleted. A file of the same name that is
        /// not KMRP's is left alone, and said so.</summary>
        private static void WriteKpatch(string path, byte[] data, string patchId, InstallJournal records,
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
            WriteWhole(path, data, hash => records.Add(new[] { "kpatch", path, hash, state }));
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
                FileGuard.Delete(record[1]);
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
        // On Linux KPM runs under Proton, with its settings in the game's prefix
        // (InstallPlatform.KpmSettingsPath).
        private static string KpmSettingsPath()
        {
            string path = GamePath.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "KPatchLauncher", "settings.json");
            return InstallPlatform.KpmSettingsPath(path);
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
                string path = InstallPlatform.LocalPath(JsonUnescape(match.Groups[1].Value));
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
                File.WriteAllBytes(GamePath.Combine(folder, Kpatches[i, 0]), ReadResource(Kpatches[i, 2]));
            File.WriteAllBytes(GamePath.Combine(folder, KpatchReadmeName), ReadResource("Kmrp.kpatch.readme"));
            File.WriteAllBytes(GamePath.Combine(folder, KpatchLicenseName), ReadResource("Kmrp.engine.license"));
        }

        private static void WriteManifest(string targetPath, int width, int height, List<string[]> records, bool complete)
        {
            StringBuilder text = new StringBuilder();
            text.Append("version\t").Append(GoldPatch.PatchVersion).Append("\r\n");
            // The build's date, which a later installer compares with its own
            // (CompareInstalled). An older installer's ReadRecords skips the line.
            if (BuildStamp.Current.HasValue)
                text.Append("built\t").Append(BuildStamp.Text(BuildStamp.Current.Value)).Append("\r\n");
            text.Append("resolution\t").Append(width.ToString(CultureInfo.InvariantCulture)).Append('\t')
                .Append(height.ToString(CultureInfo.InvariantCulture)).Append("\r\n");
            foreach (string[] record in records)
                text.Append(String.Join("\t", record)).Append("\r\n");
            if (!complete)
                text.Append(IncompleteRow).Append("\r\n");
            WriteWhole(ManifestPath(targetPath), new UTF8Encoding(false).GetBytes(text.ToString()), hash => { });
        }

        private const string IncompleteRow = "incomplete";

        // A restore acts on these names, so only what Install writes is accepted: a file
        // in the game folder or its patches\ folder, and the one rename.
        private static bool IsValidRow(string[] parts)
        {
            return (parts.Length == 3 && parts[0] == "file" && IsOwnedName(parts[1])) ||
                (parts.Length == 4 && parts[0] == "moved" && parts[1] == BinkName && parts[2] == BinkMovedName) ||
                (parts.Length == 2 && parts[0] == "laa") ||
                (parts.Length == 3 && parts[0] == "ini") ||
                (parts.Length == 2 && parts[0] == "options" &&
                 (parts[1] == OptionsName || parts[1] == ControllerOptionsName)) ||
                (parts.Length == 4 && parts[0] == "kpatch" && IsKpatchPath(parts[1]) &&
                 (parts[3] == "created" || parts[3] == "replaced"));
        }

        /// <summary>What is wrong with the manifest here, or null: unreadable, without the
        /// version row every install has written first since the first one, or holding a
        /// row of a kind Install writes that Install could not have written. Rows of other
        /// kinds are a later build's, and a .kpatch row of the right shape may name a path
        /// on another system, as a Windows install read under Linux does; ReadRecords
        /// skips both.</summary>
        private static string ManifestDamage(string targetPath)
        {
            if (!IsInstalled(targetPath))
                return null;
            try
            {
                string[] lines = File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8);
                if (lines.Length == 0 || !lines[0].StartsWith("version\t", StringComparison.Ordinal))
                    return "it has no version row";
                foreach (string line in lines)
                {
                    string[] parts = line.Split('\t');
                    if (Array.IndexOf(new[] { "file", "moved", "laa", "ini", "options", "kpatch" }, parts[0]) >= 0 &&
                        !IsValidRow(parts) && !(parts[0] == "kpatch" && parts.Length == 4))
                        return "this row is not one KMRP writes: " + line;
                }
                return null;
            }
            catch (IOException error) { return error.Message; }
            catch (UnauthorizedAccessException error) { return error.Message; }
        }

        /// <summary>Stops an install or restore before it changes anything when the manifest
        /// cannot be trusted. Until 2026-11-01 an unreadable one read as empty: a restore
        /// removed nothing, deleted the manifest and reported success, with KMRP still
        /// installed and nothing left to say what it had put there (audit INS-05).</summary>
        private static void RequireReadableManifest(string targetPath)
        {
            string damage = ManifestDamage(targetPath);
            if (damage != null)
                throw new InvalidDataException("KMRP's record of this install, " + KmrpFolder.KpmManifest +
                    ", is damaged (" + damage + "), so KMRP cannot tell which files are its own. No changes " +
                    "were made. Put the game's files back (Steam's Verify integrity, or a reinstall of the " +
                    "game), delete that file, and install again.");
        }

        private static List<string[]> ReadRecords(string targetPath)
        {
            List<string[]> records = new List<string[]>();
            try
            {
                foreach (string line in File.ReadAllLines(ManifestPath(targetPath), Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (IsValidRow(parts))
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

    /// <summary>The time an install or upgrade has left, shown under the window's button
    /// from the moment it starts and counted down a second at a time (the maintainer,
    /// 2026-10-19: "the estimate should be from the start ... not only during the art part
    /// ... and it should count down second by second").
    ///
    /// Before the art it is a few seconds for the files and, for the art, the resolutions
    /// the display offers at the pace measured on the maintainer's PC
    /// (ArtPreparation.SecondsPerResolution), shared between the workers. While the art is
    /// made, each worker is followed on its own: the parts it has done, when it last finished
    /// one, how many it has left, and its pace from its own parts (or, until it has finished
    /// one, the others' or the measured one), a tenth more to be safe. What a worker has left
    /// is its parts to come at that pace, less what it has spent on the one under way, and
    /// never less than the parts after that one; the time left is the slowest worker's.
    /// Counting resolutions alone, all workers together, the first try said "almost done"
    /// for a whole round at the end, and with the workers a little apart jumped up at the
    /// start of every round (a simulated install, 2026-10-19).
    ///
    /// What is shown never goes up (the maintainer: "it shouldn't increase again ... it
    /// should be fairly smooth ... it should overestimate instead of underestimating"): it
    /// counts down a second a second while the estimate agrees, slower when the estimate
    /// says the work is slower, holding when it says more time than is shown, and faster,
    /// up to three seconds a second, when the work is ahead, so a drop is a quick count, not
    /// a jump. The first guess is set above the measured pace for the drive the cache is on
    /// (ArtPreparation.SecondsPerResolution), so a hold is rare. It is shown again every
    /// second. The progress text carries it after a tab, which the window splits off
    /// (MainForm.RunOperation, timeLeftLabel); at 100% there is none.</summary>
    internal sealed class InstallClock
    {
        private readonly object gate = new object();
        private readonly Stopwatch clock = Stopwatch.StartNew();
        private readonly Action<int, string> progress;
        private readonly double filesExpected, perPart;
        private readonly int expectedSizes;
        private readonly System.Threading.Timer ticker;
        // Per worker: parts done, parts in all (-1 until it says), when it last finished one.
        private readonly int[] done, total;
        private readonly double[] finished;
        private int percent;
        private string message = String.Empty;
        private double artBegun = -1;
        private double shown = -1, shownAt;
        private bool stopped;

        internal InstallClock(Action<int, string> progress, double filesExpected, int expectedSizes, int workers,
            double perPart)
        {
            this.progress = progress;
            this.filesExpected = filesExpected;
            this.expectedSizes = Math.Max(1, expectedSizes);
            this.perPart = perPart;
            int count = Math.Max(1, workers);
            done = new int[count];
            total = new int[count];
            finished = new double[count];
            for (int i = 0; i < count; i++)
                total[i] = -1;
            ticker = new System.Threading.Timer(delegate { Tick(); }, null, 1000, 1000);
        }

        /// <summary>A step of the install, as SafeProgress reports one.</summary>
        internal void Report(int value, string text)
        {
            lock (gate)
            {
                percent = value;
                message = text ?? String.Empty;
                Emit();
            }
        }

        internal void ArtBegun()
        {
            lock (gate)
                if (artBegun < 0)
                    artBegun = clock.Elapsed.TotalSeconds;
        }

        /// <summary>Worker `index` has done `parts` of its `all` (its first, for the first
        /// worker, the common files).</summary>
        internal void ArtWorker(int index, int parts, int all)
        {
            lock (gate)
            {
                if (index < 0 || index >= done.Length)
                    return;
                double now = clock.Elapsed.TotalSeconds;
                if (artBegun < 0)
                    artBegun = now;
                if (parts != done[index])
                    finished[index] = now;
                done[index] = parts;
                total[index] = all;
            }
        }

        internal void Stop()
        {
            lock (gate)
                stopped = true;
            ticker.Dispose();
        }

        private void Tick()
        {
            lock (gate)
                Emit();
        }

        private double Remaining(double now)
        {
            int workers = done.Length;
            // A worker's share until it says: the measured pace's parts, the first worker's
            // with the common files.
            int share = (int)Math.Ceiling((double)expectedSizes / workers);
            if (artBegun < 0)
                return Math.Max(1, filesExpected - now) + 2 + (share + 1) * perPart;
            double paces = 0;
            int timed = 0;
            for (int i = 0; i < workers; i++)
                if (done[i] > 0)
                {
                    paces += (finished[i] - artBegun) / done[i];
                    timed++;
                }
            // A tenth above what has been measured, so the estimate errs high.
            const double Margin = 1.1;
            double typical = timed > 0 ? Margin * paces / timed : perPart;
            double longest = 0;
            for (int i = 0; i < workers; i++)
            {
                int all = total[i] >= 0 ? total[i] : share + (i == 0 ? 1 : 0);
                int left = all - done[i];
                if (left <= 0)
                    continue;
                double pace = done[i] > 0 ? Margin * (finished[i] - artBegun) / done[i] : typical;
                double since = now - (done[i] > 0 ? finished[i] : artBegun);
                double mine = Math.Max(left * pace - since, (left - 1) * pace + 1);
                if (mine > longest)
                    longest = mine;
            }
            return longest;
        }

        // Called under the lock, so nothing is shown once the install is over; the window's
        // progress is posted to it, not waited for.
        private void Emit()
        {
            if (stopped)
                return;
            double now = clock.Elapsed.TotalSeconds;
            double target = Remaining(now);
            if (shown < 0)
                shown = target;
            else
            {
                double step = now - shownAt;
                if (target < shown - 3 * step)
                    shown -= 3 * step;      // ahead: down quickly, not in a jump
                else if (target < shown)
                    shown = target;         // a second a second, or slower
                // else: behind the estimate, held; never up
            }
            shownAt = now;
            int seconds = (int)Math.Ceiling(shown);
            try { progress(percent, percent >= 100 ? message : message + "\t" + TimeLeft(seconds)); }
            catch { }
        }

        /// <summary>The time left as the window shows it, to the second.</summary>
        internal static string TimeLeft(int seconds)
        {
            if (seconds <= 1)
                return "almost done";
            if (seconds < 60)
                return seconds.ToString(CultureInfo.InvariantCulture) + " s left";
            return (seconds / 60).ToString(CultureInfo.InvariantCulture) + " min " +
                (seconds % 60).ToString(CultureInfo.InvariantCulture) + " s left";
        }
    }
}
