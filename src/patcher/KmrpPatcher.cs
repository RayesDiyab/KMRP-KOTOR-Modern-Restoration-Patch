using System;
using System.ComponentModel;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Drawing.Text;
using Microsoft.Win32;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace Kmrp
{
    internal sealed class DpiCompatibilityEditState
    {
        internal string ExecutablePath;
        internal bool HadRegistryValue;
        internal string RegistryValue;
        internal bool HadManifest;
        internal byte[] ManifestBytes;
        internal bool Changed;
    }

    /// <summary>Opts the game executable out of Windows DPI virtualization.
    ///
    /// KMRP already scales KOTOR's interface for the selected framebuffer. If Windows
    /// applies its own compatibility scaling on top, a 3840x2160 game at 150% desktop
    /// scaling is rendered as though its usable surface were smaller and the UI appears
    /// zoomed. The Properties -> Compatibility -> High DPI override -> Application fix
    /// writes HIGHDPIAWARE to this per-user AppCompat value.
    ///
    /// A sidecar preserves the exact value that existed before KMRP added its token.
    /// Restore changes the registry only while it still equals the value KMRP wrote;
    /// a later user or Windows change is left untouched.</summary>
    internal static class DpiCompatibilityOperations
    {
        private const string LayersKeyPath = @"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers";
        private const string Token = "HIGHDPIAWARE";
        private const string ManifestHeader = "KMRPDPI1";

        private sealed class DpiRecord
        {
            internal string ExecutablePath;
            internal bool HadPreviousValue;
            internal string PreviousValue;
            internal string InstalledValue;
        }

        // KMRP\dpi.manifest (KmrpFolder); KMRP_DPI.manifest in the game folder until 2026-10-20.
        private static string ManifestPath(string executablePath)
        {
            return KmrpFolder.PathOf(executablePath, KmrpFolder.DpiManifest);
        }

        internal static DpiCompatibilityEditState Install(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            string manifestPath = ManifestPath(executablePath);
            DpiCompatibilityEditState state = new DpiCompatibilityEditState();
            state.ExecutablePath = executablePath;
            state.HadManifest = File.Exists(manifestPath);
            state.ManifestBytes = state.HadManifest ? File.ReadAllBytes(manifestPath) : null;

            try
            {
                using (RegistryKey key = Registry.CurrentUser.CreateSubKey(LayersKeyPath))
                {
                    if (key == null)
                        throw new IOException("The Windows compatibility settings key could not be opened.");

                    object raw = key.GetValue(executablePath, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                    state.HadRegistryValue = raw != null;
                    state.RegistryValue = raw as string;
                    if (raw != null && state.RegistryValue == null)
                        throw new InvalidDataException("The existing Windows compatibility setting is not a string value.");

                    // A Windows compatibility mode on swkotor.exe ("Run this program in
                    // compatibility mode for", reduced colour, 640x480) is taken out with
                    // KMRP's token: with one on, the game drew a black square over most of
                    // the screen after patching (issue 39; the reporter turned it off by
                    // hand, 2026-10-16). Restore Original puts the value back as it was.
                    List<string> removed;
                    string cleaned = WithoutCompatibilityModes(state.RegistryValue, out removed);
                    string installed = ContainsToken(cleaned, Token) ? cleaned : AppendToken(cleaned, Token);
                    ReportMachineWideMode(executablePath, report);
                    if (String.Equals(installed, state.RegistryValue, StringComparison.Ordinal))
                    {
                        SafeReport(report, "Verified the Windows high-DPI application override for swkotor.exe.");
                        return state;
                    }

                    DpiRecord record = new DpiRecord();
                    record.ExecutablePath = executablePath;
                    record.HadPreviousValue = state.HadRegistryValue;
                    record.PreviousValue = state.RegistryValue ?? String.Empty;
                    // Patching again over KMRP: the value now is the one KMRP wrote, so the
                    // first install's record keeps what was there before KMRP.
                    DpiRecord earlier = TryReadManifest(manifestPath);
                    if (earlier != null && String.Equals(earlier.InstalledValue, state.RegistryValue, StringComparison.Ordinal))
                    {
                        record.HadPreviousValue = earlier.HadPreviousValue;
                        record.PreviousValue = earlier.PreviousValue;
                    }
                    record.InstalledValue = installed;

                    try
                    {
                        key.SetValue(executablePath, installed, RegistryValueKind.String);
                        object verified = key.GetValue(executablePath, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                        if (!String.Equals(verified as string, installed, StringComparison.Ordinal))
                            throw new IOException("The Windows high-DPI compatibility setting could not be verified.");
                        WriteManifest(manifestPath, record);
                    }
                    catch
                    {
                        RestoreRegistryValue(key, executablePath, state.HadRegistryValue, state.RegistryValue);
                        throw;
                    }
                    state.Changed = true;
                    if (removed.Count > 0)
                        SafeReport(report, "Turned off Windows compatibility mode for swkotor.exe (" + String.Join(", ", removed.ToArray()) +
                            "): it draws a black square over the game with KMRP. Restore Original turns it back on.");
                    if (!ContainsToken(state.RegistryValue, Token))
                        SafeReport(report, "Enabled the Windows high-DPI application override for swkotor.exe.");
                    return state;
                }
            }
            catch (UnauthorizedAccessException ex)
            {
                SafeReport(report, "Windows high-DPI handling could not be configured automatically: " + ex.Message +
                    " Set swkotor.exe Compatibility -> High DPI scaling override to Application.");
                return state;
            }
            catch (System.Security.SecurityException ex)
            {
                SafeReport(report, "Windows high-DPI handling could not be configured automatically: " + ex.Message +
                    " Set swkotor.exe Compatibility -> High DPI scaling override to Application.");
                return state;
            }
        }

        internal static void Rollback(DpiCompatibilityEditState state)
        {
            if (state == null || !state.Changed)
                return;
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(LayersKeyPath))
            {
                if (key == null)
                    throw new IOException("The Windows compatibility settings key could not be opened for rollback.");
                RestoreRegistryValue(key, state.ExecutablePath, state.HadRegistryValue, state.RegistryValue);
            }
            string manifestPath = ManifestPath(state.ExecutablePath);
            if (state.HadManifest)
                File.WriteAllBytes(manifestPath, state.ManifestBytes);
            else if (File.Exists(manifestPath))
                File.Delete(manifestPath);
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;

            DpiRecord record = ReadManifest(manifestPath);
            // The setting is filed under the path the game had at install. Until
            // 2026-10-10 any other path stopped the whole restore here, after the
            // patches were removed and before swkotor.ini was put back (issue 36):
            // under Wine one folder has several paths (S:\ and Z:\ under Proton), and
            // on Windows a game folder moved after install has a new one. The record's
            // path is used when the game is no longer there or is this same folder; a
            // game still at that path in another folder is a different install, whose
            // setting is left alone.
            string valueName = executablePath;
            if (!String.Equals(record.ExecutablePath, executablePath, StringComparison.OrdinalIgnoreCase))
            {
                if (File.Exists(record.ExecutablePath) && !SameFolder(record.ExecutablePath, executablePath))
                {
                    File.Delete(manifestPath);
                    SafeReport(report, "Left the Windows high-DPI compatibility setting alone: it was recorded for " +
                        "another copy of the game, " + record.ExecutablePath + ".");
                    return;
                }
                valueName = record.ExecutablePath;
            }

            bool restored = false;
            bool kept = false;
            using (RegistryKey key = Registry.CurrentUser.CreateSubKey(LayersKeyPath))
            {
                if (key == null)
                    throw new IOException("The Windows compatibility settings key could not be opened for restore.");
                object raw = key.GetValue(valueName, null, RegistryValueOptions.DoNotExpandEnvironmentNames);
                string current = raw as string;
                if (raw != null && current == null)
                {
                    kept = true;
                }
                else if (String.Equals(current, record.InstalledValue, StringComparison.Ordinal))
                {
                    RestoreRegistryValue(key, valueName, record.HadPreviousValue, record.PreviousValue);
                    restored = true;
                }
                else
                {
                    kept = true;
                }
            }

            File.Delete(manifestPath);
            if (restored)
                SafeReport(report, "Restored the previous Windows high-DPI compatibility setting.");
            if (kept)
                SafeReport(report, "Left the Windows high-DPI compatibility setting in place because it changed after install.");
        }

        /// <summary>Whether two paths of swkotor.exe name the same file in the same
        /// folder: a file made beside one is seen beside the other. False when that
        /// cannot be tried.</summary>
        private static bool SameFolder(string recordedPath, string executablePath)
        {
            string probe = "KMRP_DPI." + Guid.NewGuid().ToString("N") + ".tmp";
            string here = Path.Combine(Path.GetDirectoryName(executablePath), probe);
            try
            {
                string there = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(recordedPath)), probe);
                File.WriteAllBytes(here, new byte[0]);
                return File.Exists(there);
            }
            catch
            {
                return false;
            }
            finally
            {
                try { File.Delete(here); }
                catch { }
            }
        }

        /// <summary>The Compatibility tab's layers that break KMRP's screen: the Windows
        /// version modes and the reduced colour and 640x480 settings. Others (high DPI, run
        /// as administrator, full-screen optimisations) are kept.</summary>
        private static readonly string[] CompatibilityModes =
        {
            "WIN95", "WIN98", "NT4SP5", "WIN2000", "WINXP", "WINXPSP2", "WINXPSP3", "WINSRV03SP1",
            "WINSRV08SP1", "VISTARTM", "VISTASP1", "VISTASP2", "WIN7RTM", "WIN8RTM", "WIN81RTM",
            "256COLOR", "16BITCOLOR", "640X480"
        };

        private static bool IsCompatibilityMode(string token)
        {
            foreach (string mode in CompatibilityModes)
                if (String.Equals(token, mode, StringComparison.OrdinalIgnoreCase))
                    return true;
            return false;
        }

        /// <summary>The value without its compatibility modes, its other tokens in order;
        /// a value left with only Windows' "~" marker is left empty.</summary>
        private static string WithoutCompatibilityModes(string value, out List<string> removed)
        {
            removed = new List<string>();
            if (String.IsNullOrWhiteSpace(value))
                return value;
            List<string> kept = new List<string>();
            foreach (string part in Regex.Split(value.Trim(), "\\s+"))
            {
                if (IsCompatibilityMode(part))
                    removed.Add(part.ToUpperInvariant());
                else
                    kept.Add(part);
            }
            if (removed.Count == 0)
                return value;
            if (kept.Count == 1 && kept[0] == "~")
                kept.Clear();
            return String.Join(" ", kept.ToArray());
        }

        /// <summary>"Change settings for all users" keeps the mode in the machine's part of
        /// the registry, which the installer (not run as administrator) cannot change: it
        /// says what to turn off instead.</summary>
        private static void ReportMachineWideMode(string executablePath, Action<string> report)
        {
            try
            {
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(LayersKeyPath))
                {
                    string value = key == null ? null : key.GetValue(executablePath, null) as string;
                    List<string> modes;
                    WithoutCompatibilityModes(value, out modes);
                    if (modes.Count > 0)
                        SafeReport(report, "Windows compatibility mode is on for swkotor.exe for all users (" +
                            String.Join(", ", modes.ToArray()) + "). It draws a black square over the game with KMRP. " +
                            "Turn it off: swkotor.exe, Properties, Compatibility, Change settings for all users.");
                }
            }
            catch { }
        }

        private static DpiRecord TryReadManifest(string path)
        {
            try
            {
                return File.Exists(path) ? ReadManifest(path) : null;
            }
            catch
            {
                return null;
            }
        }

        private static bool ContainsToken(string value, string token)
        {
            if (String.IsNullOrWhiteSpace(value))
                return false;
            foreach (string part in Regex.Split(value.Trim(), "\\s+"))
                if (String.Equals(part, token, StringComparison.OrdinalIgnoreCase))
                    return true;
            return false;
        }

        private static string AppendToken(string value, string token)
        {
            if (String.IsNullOrWhiteSpace(value))
                return token;
            return value.TrimEnd() + " " + token;
        }

        private static void RestoreRegistryValue(RegistryKey key, string name, bool hadValue, string value)
        {
            if (hadValue)
                key.SetValue(name, value ?? String.Empty, RegistryValueKind.String);
            else
                key.DeleteValue(name, false);
        }

        private static void WriteManifest(string path, DpiRecord record)
        {
            string text = ManifestHeader + "\r\n" +
                Encode(record.ExecutablePath) + "\r\n" +
                (record.HadPreviousValue ? "1" : "0") + "\r\n" +
                Encode(record.PreviousValue) + "\r\n" +
                Encode(record.InstalledValue) + "\r\n";
            File.WriteAllText(path, text, new UTF8Encoding(false));
        }

        private static DpiRecord ReadManifest(string path)
        {
            string[] lines = File.ReadAllLines(path, Encoding.UTF8);
            if (lines.Length != 5 || lines[0] != ManifestHeader ||
                (lines[2] != "0" && lines[2] != "1"))
                throw new InvalidDataException("The Windows high-DPI manifest is invalid. Restore was blocked.");
            DpiRecord record = new DpiRecord();
            record.ExecutablePath = Decode(lines[1]);
            record.HadPreviousValue = lines[2] == "1";
            record.PreviousValue = Decode(lines[3]);
            record.InstalledValue = Decode(lines[4]);
            if (!ContainsToken(record.InstalledValue, Token))
                throw new InvalidDataException("The Windows high-DPI manifest does not contain the installed setting.");
            return record;
        }

        private static string Encode(string value)
        {
            return Convert.ToBase64String(Encoding.UTF8.GetBytes(value ?? String.Empty));
        }

        private static string Decode(string value)
        {
            try { return Encoding.UTF8.GetString(Convert.FromBase64String(value)); }
            catch (FormatException ex)
            {
                throw new InvalidDataException("The Windows high-DPI manifest contains invalid text.", ex);
            }
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report == null)
                return;
            try { report(message); }
            catch { }
        }
    }

    /// <summary>The slice of NVIDIA's driver-settings interface (NvAPI DRS) the patcher
    /// uses. Entry points are the documented ones from nvapi_interface.h, fetched through
    /// nvapi_QueryInterface; structures are marshalled by explicit offset from nvapi.h,
    /// where every string is NVAPI_UNICODE_STRING_MAX = 2048 UTF-16 units and every other
    /// field is 32-bit, so the layouts have no padding:
    ///
    ///   NVDRS_SETTING v1      12320 bytes  version 0, settingId 4100, settingType 4104,
    ///                                      settingLocation 4108, currentValue 8220
    ///   NVDRS_APPLICATION v4  20492 bytes  version 0, appName 8
    ///   NVDRS_PROFILE v1       4116 bytes  version 0, profileName 4, numOfApps 4108,
    ///                                      numOfSettings 4112
    ///
    /// A struct's version word is its size | (version &lt;&lt; 16), NVAPI's MAKE_NVAPI_VERSION.</summary>
    internal sealed class NvDrsSession : IDisposable
    {
        internal const int Ok = 0;
        internal const int InvalidUserPrivilege = -137;
        private const int SettingNotFound = -160;
        private const int ProfileNotFound = -163;
        private const int ExecutableNotFound = -166;
        internal const int LocationCurrentProfile = 0;   // NVDRS_CURRENT_PROFILE_LOCATION

        private const int StringBytes = 4096;
        private const int SettingSize = 12320;
        private const int SettingIdOffset = 4100;
        private const int SettingTypeOffset = 4104;
        private const int SettingLocationOffset = 4108;
        private const int SettingCurrentOffset = 8220;
        private const int ApplicationSize = 20492;
        private const int ApplicationNameOffset = 8;
        private const int ProfileSize = 4116;
        private const int ProfileNameOffset = 4;
        private const int ProfileAppsOffset = 4108;
        private const int ProfileSettingsOffset = 4112;

        private const uint LoadLibrarySearchSystem32 = 0x00000800;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibraryEx(string name, IntPtr reserved, uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Ansi, SetLastError = true)]
        private static extern IntPtr GetProcAddress(IntPtr module, string name);

        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate IntPtr QueryInterfaceFn(uint id);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int NoArgFn();
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int HandleOutFn(out IntPtr handle);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int SessionFn(IntPtr session);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int SessionHandleOutFn(IntPtr session, out IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int FindApplicationFn(IntPtr session, IntPtr appName, out IntPtr profile, IntPtr application);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int FindProfileFn(IntPtr session, IntPtr profileName, out IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int CreateProfileFn(IntPtr session, IntPtr profileInfo, out IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int ProfileFn(IntPtr session, IntPtr profile);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int ProfileStructFn(IntPtr session, IntPtr profile, IntPtr data);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int GetSettingFn(IntPtr session, IntPtr profile, uint settingId, IntPtr setting);
        [UnmanagedFunctionPointer(CallingConvention.Cdecl)]
        private delegate int DeleteSettingFn(IntPtr session, IntPtr profile, uint settingId);

        private readonly NoArgFn unload;
        private readonly SessionFn destroySession;
        private readonly SessionFn saveSettings;
        private readonly FindApplicationFn findApplication;
        private readonly FindProfileFn findProfile;
        private readonly SessionHandleOutFn globalProfile;
        private readonly CreateProfileFn createProfile;
        private readonly ProfileFn deleteProfile;
        private readonly ProfileStructFn profileInfo;
        private readonly ProfileStructFn createApplication;
        private readonly GetSettingFn getSetting;
        private readonly ProfileStructFn setSetting;
        private readonly DeleteSettingFn deleteSetting;
        private IntPtr session;

        private NvDrsSession(QueryInterfaceFn query)
        {
            unload = Function<NoArgFn>(query, 0xD22BDD7E);
            destroySession = Function<SessionFn>(query, 0xDAD9CFF8);
            saveSettings = Function<SessionFn>(query, 0xFCBC7E14);
            findApplication = Function<FindApplicationFn>(query, 0xEEE566B2);
            findProfile = Function<FindProfileFn>(query, 0x7E4A9A0B);
            globalProfile = Function<SessionHandleOutFn>(query, 0x617BFF9F);
            createProfile = Function<CreateProfileFn>(query, 0xCC176068);
            deleteProfile = Function<ProfileFn>(query, 0x17093206);
            profileInfo = Function<ProfileStructFn>(query, 0x61CD6FD6);
            createApplication = Function<ProfileStructFn>(query, 0x4347A9DE);
            getSetting = Function<GetSettingFn>(query, 0x73BF8338);
            setSetting = Function<ProfileStructFn>(query, 0x577DD202);
            deleteSetting = Function<DeleteSettingFn>(query, 0xE4A26362);
        }

        /// <summary>A loaded driver-settings session, or null with the reason when there is
        /// no NVIDIA driver to talk to. nvapi is loaded from System32 only, never from the
        /// patcher's own folder.</summary>
        internal static NvDrsSession TryOpen(out string unavailable)
        {
            IntPtr module = LoadLibraryEx(IntPtr.Size == 8 ? "nvapi64.dll" : "nvapi.dll",
                IntPtr.Zero, LoadLibrarySearchSystem32);
            if (module == IntPtr.Zero)
            {
                unavailable = "no NVIDIA driver is installed";
                return null;
            }
            IntPtr queryAddress = GetProcAddress(module, "nvapi_QueryInterface");
            if (queryAddress == IntPtr.Zero)
            {
                unavailable = "nvapi has no nvapi_QueryInterface";
                return null;
            }
            QueryInterfaceFn query = (QueryInterfaceFn)Marshal.GetDelegateForFunctionPointer(
                queryAddress, typeof(QueryInterfaceFn));
            NoArgFn initialize = Function<NoArgFn>(query, 0x0150E828);
            int status = initialize();
            if (status != Ok)
            {
                unavailable = "NvAPI_Initialize returned " + status.ToString(CultureInfo.InvariantCulture);
                return null;
            }
            NvDrsSession drs = new NvDrsSession(query);
            try
            {
                HandleOutFn create = Function<HandleOutFn>(query, 0x0694D52E);
                Check("NvAPI_DRS_CreateSession", create(out drs.session));
                Check("NvAPI_DRS_LoadSettings", Function<SessionFn>(query, 0x375DBD6B)(drs.session));
            }
            catch
            {
                drs.Dispose();
                throw;
            }
            unavailable = null;
            return drs;
        }

        /// <summary>The profile the driver applies to this executable, or zero when no
        /// profile names it. Given a full path, NvAPI answers for that path.</summary>
        internal IntPtr FindApplicationProfile(string executablePath)
        {
            IntPtr name = NewString(executablePath);
            IntPtr application = NewStruct(ApplicationSize, 4);
            try
            {
                IntPtr profile;
                int status = findApplication(session, name, out profile, application);
                if (status == ExecutableNotFound)
                    return IntPtr.Zero;
                Check("NvAPI_DRS_FindApplicationByName", status);
                return profile;
            }
            finally
            {
                Marshal.FreeHGlobal(name);
                Marshal.FreeHGlobal(application);
            }
        }

        internal IntPtr GlobalProfile()
        {
            IntPtr profile;
            Check("NvAPI_DRS_GetCurrentGlobalProfile", globalProfile(session, out profile));
            return profile;
        }

        internal IntPtr FindProfile(string profileName)
        {
            IntPtr name = NewString(profileName);
            try
            {
                IntPtr profile;
                int status = findProfile(session, name, out profile);
                if (status == ProfileNotFound)
                    return IntPtr.Zero;
                Check("NvAPI_DRS_FindProfileByName", status);
                return profile;
            }
            finally
            {
                Marshal.FreeHGlobal(name);
            }
        }

        internal IntPtr CreateProfile(string profileName)
        {
            IntPtr info = NewStruct(ProfileSize, 1);
            try
            {
                WriteString(info, ProfileNameOffset, profileName);
                IntPtr profile;
                Check("NvAPI_DRS_CreateProfile", createProfile(session, info, out profile));
                return profile;
            }
            finally
            {
                Marshal.FreeHGlobal(info);
            }
        }

        internal void DeleteProfile(IntPtr profile)
        {
            Check("NvAPI_DRS_DeleteProfile", deleteProfile(session, profile));
        }

        /// <summary>The profile's name and how many applications and settings it holds.</summary>
        internal void ProfileInfo(IntPtr profile, out string name, out int applications, out int settings)
        {
            IntPtr info = NewStruct(ProfileSize, 1);
            try
            {
                Check("NvAPI_DRS_GetProfileInfo", profileInfo(session, profile, info));
                name = Marshal.PtrToStringUni(new IntPtr(info.ToInt64() + ProfileNameOffset));
                applications = Marshal.ReadInt32(info, ProfileAppsOffset);
                settings = Marshal.ReadInt32(info, ProfileSettingsOffset);
            }
            finally
            {
                Marshal.FreeHGlobal(info);
            }
        }

        internal void AddApplication(IntPtr profile, string applicationName)
        {
            IntPtr application = NewStruct(ApplicationSize, 4);
            try
            {
                WriteString(application, ApplicationNameOffset, applicationName);
                Check("NvAPI_DRS_CreateApplication", createApplication(session, profile, application));
            }
            finally
            {
                Marshal.FreeHGlobal(application);
            }
        }

        /// <summary>The setting's value as the driver resolves it for this profile, and
        /// where that value comes from: the profile itself (LocationCurrentProfile), or
        /// the global, base or default profile it inherits from. False when no profile
        /// holds the setting at all.</summary>
        internal bool TryGetDword(IntPtr profile, uint settingId, out uint value, out int location)
        {
            IntPtr setting = NewStruct(SettingSize, 1);
            try
            {
                int status = getSetting(session, profile, settingId, setting);
                if (status == SettingNotFound)
                {
                    value = 0;
                    location = -1;
                    return false;
                }
                Check("NvAPI_DRS_GetSetting", status);
                value = unchecked((uint)Marshal.ReadInt32(setting, SettingCurrentOffset));
                location = Marshal.ReadInt32(setting, SettingLocationOffset);
                return true;
            }
            finally
            {
                Marshal.FreeHGlobal(setting);
            }
        }

        internal void SetDword(IntPtr profile, uint settingId, uint value)
        {
            IntPtr setting = NewStruct(SettingSize, 1);
            try
            {
                Marshal.WriteInt32(setting, SettingIdOffset, unchecked((int)settingId));
                Marshal.WriteInt32(setting, SettingTypeOffset, 0);   // NVDRS_DWORD_TYPE
                Marshal.WriteInt32(setting, SettingCurrentOffset, unchecked((int)value));
                Check("NvAPI_DRS_SetSetting", setSetting(session, profile, setting));
            }
            finally
            {
                Marshal.FreeHGlobal(setting);
            }
        }

        internal void DeleteSetting(IntPtr profile, uint settingId)
        {
            int status = deleteSetting(session, profile, settingId);
            if (status != SettingNotFound)
                Check("NvAPI_DRS_DeleteProfileSetting", status);
        }

        /// <summary>Writes the session's changes to the driver. Returned rather than
        /// thrown, because InvalidUserPrivilege has a useful answer.</summary>
        internal int Save()
        {
            return saveSettings(session);
        }

        public void Dispose()
        {
            if (session != IntPtr.Zero)
            {
                destroySession(session);
                session = IntPtr.Zero;
            }
            unload();
        }

        private static T Function<T>(QueryInterfaceFn query, uint id) where T : class
        {
            IntPtr address = query(id);
            if (address == IntPtr.Zero)
                throw new NotSupportedException("This NVIDIA driver does not provide NvAPI function 0x" +
                    id.ToString("X8", CultureInfo.InvariantCulture) + ".");
            return (T)(object)Marshal.GetDelegateForFunctionPointer(address, typeof(T));
        }

        private static void Check(string function, int status)
        {
            if (status != Ok)
                throw new IOException(function + " returned " + status.ToString(CultureInfo.InvariantCulture) + ".");
        }

        private static IntPtr NewStruct(int size, int version)
        {
            IntPtr block = Marshal.AllocHGlobal(size);
            Marshal.Copy(new byte[size], 0, block, size);
            Marshal.WriteInt32(block, 0, size | (version << 16));
            return block;
        }

        private static IntPtr NewString(string value)
        {
            IntPtr block = Marshal.AllocHGlobal(StringBytes);
            Marshal.Copy(new byte[StringBytes], 0, block, StringBytes);
            WriteString(block, 0, value);
            return block;
        }

        private static void WriteString(IntPtr block, int offset, string value)
        {
            byte[] text = Encoding.Unicode.GetBytes(value ?? String.Empty);
            if (text.Length > StringBytes - 2)
                throw new ArgumentException("An NvAPI string is limited to 2047 characters.");
            Marshal.Copy(text, 0, new IntPtr(block.ToInt64() + offset), text.Length);
        }
    }

    /// <summary>Removes the NVIDIA present method older KMRP installs set.
    ///
    /// From 2026-09-19 to 2026-10-30 KMRP set NVIDIA's "Vulkan/OpenGL present method"
    /// for swkotor.exe to "Prefer native" wherever the game would inherit "Prefer layered
    /// on DXGI Swapchain", because that path showed half-drawn frames (issue 14). That also
    /// took Windows Auto HDR and RTX HDR away from players who chose layered for them
    /// (issue 73). Since 2026-10-30 KMRP's module draws each frame offscreen and shows it
    /// finished (K1OffscreenFrame.cpp), so KMRP sets nothing. The installer and the module
    /// both wrote the value, and both recorded it in KMRP's nvidia.manifest.
    ///
    /// Restore runs at every install and every restore. With a record, it removes KMRP's
    /// value while the game's profile still holds it (the whole profile when KMRP made it
    /// and nothing was added since) and drops the record; a value the player changed since
    /// is left. Without a record nothing is touched. None of this may fail an install.
    /// See docs/nvidia-present-method.md.</summary>
    internal static class NvidiaPresentOperations
    {
        // NvApiDriverSettings.h: OGL_CPL_PREFER_DXPRESENT, "Vulkan/OpenGL present method".
        private const uint PresentMethodId = 0x20D690F8;
        private const uint PreferNative = 0;    // OGL_CPL_PREFER_DXPRESENT_PREFER_DISABLED
        private const uint PreferLayered = 1;   // OGL_CPL_PREFER_DXPRESENT_PREFER_ENABLED
        private const uint PresentAuto = 2;     // OGL_CPL_PREFER_DXPRESENT_AUTO, the default
        internal const string ProfileName = "KMRP - Star Wars: Knights of the Old Republic";
        private const string ManifestHeader = "KMRPNV1";

        // KMRP\nvidia.manifest (KmrpFolder); KMRP_NVIDIA.manifest in the game folder until 2026-10-20.
        private static string ManifestPath(string executablePath)
        {
            return KmrpFolder.PathOf(executablePath, KmrpFolder.NvidiaManifest);
        }

        internal static void Restore(string executablePath, Action<string> report)
        {
            executablePath = Path.GetFullPath(executablePath);
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;

            try
            {
                bool createdProfile;
                string recordedPath = ReadManifest(manifestPath, out createdProfile);
                if (!String.Equals(recordedPath, executablePath, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("the NVIDIA manifest belongs to a different executable path.");

                bool restored = false;
                string unavailable;
                using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
                {
                    if (drs == null)
                    {
                        // Unavailable can mean a transient driver/service failure;
                        // it does not prove that the saved profile was deleted.
                        SafeReport(report, "Kept KMRP's NVIDIA present-method record for a later restore: " + unavailable + ".");
                        return;
                    }
                    IntPtr profile = drs.FindApplicationProfile(executablePath);
                    uint value;
                    int location;
                    if (profile != IntPtr.Zero &&
                        drs.TryGetDword(profile, PresentMethodId, out value, out location) &&
                        location == NvDrsSession.LocationCurrentProfile && value == PreferNative)
                    {
                        string name;
                        int applications;
                        int settings;
                        drs.ProfileInfo(profile, out name, out applications, out settings);
                        // The whole profile only when KMRP made it and nothing else was
                        // added since; otherwise just the one setting.
                        if (createdProfile && name == ProfileName && applications == 1 && settings == 1)
                            drs.DeleteProfile(profile);
                        else
                            drs.DeleteSetting(profile, PresentMethodId);
                        int saved = drs.Save();
                        if (saved != NvDrsSession.Ok)
                        {
                            SafeReport(report, "KMRP's NVIDIA present-method setting for swkotor.exe could not be " +
                                "removed (NvAPI_DRS_SaveSettings returned " +
                                saved.ToString(CultureInfo.InvariantCulture) + "). Set it back to Use global " +
                                "setting in the NVIDIA Control Panel if you want the old behaviour.");
                            return;   // manifest kept, so a later restore can retry
                        }
                        restored = true;
                    }
                }

                File.Delete(manifestPath);
                if (restored)
                    SafeReport(report, "Removed KMRP's NVIDIA present-method setting for swkotor.exe.");
                else
                    SafeReport(report, "Left NVIDIA's present method for swkotor.exe as it is: it changed after install.");
            }
            catch (Exception ex)
            {
                SafeReport(report, "KMRP's NVIDIA present-method setting for swkotor.exe could not be restored: " +
                    ex.Message);
            }
        }

        /// <summary>One line on what NVIDIA will do for this executable, for logs and tests.</summary>
        internal static string Describe(string executablePath)
        {
            executablePath = Path.GetFullPath(executablePath);
            string unavailable;
            using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
            {
                if (drs == null)
                    return "NVIDIA: unavailable (" + unavailable + ")";
                IntPtr profile = drs.FindApplicationProfile(executablePath);
                IntPtr global = drs.GlobalProfile();
                uint value;
                int location;
                string game = "no profile names it";
                if (profile != IntPtr.Zero)
                {
                    string name;
                    int applications;
                    int settings;
                    drs.ProfileInfo(profile, out name, out applications, out settings);
                    game = "profile \"" + name + "\", " + (drs.TryGetDword(profile, PresentMethodId, out value, out location)
                        ? "present method " + Name(value) + " from " + Location(location)
                        : "present method not set anywhere");
                }
                string globalValue = drs.TryGetDword(global, PresentMethodId, out value, out location)
                    ? Name(value) : "not set (Auto)";
                return "NVIDIA: " + game + "; global " + globalValue +
                    (File.Exists(ManifestPath(executablePath)) ? "; KMRP manifest present" : "");
            }
        }

        private static string Name(uint value)
        {
            switch (value)
            {
                case PreferNative: return "Prefer native";
                case PreferLayered: return "Prefer layered on DXGI Swapchain";
                case PresentAuto: return "Auto";
                default: return "0x" + value.ToString("X8", CultureInfo.InvariantCulture);
            }
        }

        private static string Location(int location)
        {
            switch (location)
            {
                case 0: return "the game's own profile";
                case 1: return "the global profile";
                case 2: return "the base profile";
                case 3: return "the driver default";
                default: return "location " + location.ToString(CultureInfo.InvariantCulture);
            }
        }

        private static string ReadManifest(string path, out bool createdProfile)
        {
            string[] lines = File.ReadAllLines(path, Encoding.UTF8);
            if (lines.Length != 3 || lines[0] != ManifestHeader || (lines[2] != "0" && lines[2] != "1"))
                throw new InvalidDataException("the NVIDIA manifest is invalid.");
            createdProfile = lines[2] == "1";
            try { return Encoding.UTF8.GetString(Convert.FromBase64String(lines[1])); }
            catch (FormatException ex)
            {
                throw new InvalidDataException("the NVIDIA manifest contains invalid text.", ex);
            }
        }

        private static void SafeReport(Action<string> report, string message)
        {
            if (report == null)
                return;
            try { report(message); }
            catch { }
        }
    }

    /// <summary>Installs and removes the bundled K1 Modern Driver Compatibility patch.
    ///
    /// K1DC is by Synchro, MPL-2.0, and is shipped here as the standalone build the
    /// author publishes for exactly this case: an executable another patcher has already
    /// modified, which his Patch Manager will not recognise. See
    /// docs/third-party-driver-compat.md.
    ///
    /// It is two files dropped beside swkotor.exe -- a `dinput8.dll` proxy that Windows
    /// loads at startup, and the `.asi` payload it loads in turn. **The executable is
    /// never touched.** K1DC patches its sites in memory at run time and checks only
    /// those, which is why it does not care that KMRP changes bytes elsewhere. Version
    /// 2.0.0 since 2026-10-19 (1.2.0 until then): its 28 sites (8 in 1.2.0) hold the
    /// exact bytes his `kotor1.hooks.toml` declares in the unmodified 1.03 executable, and
    /// none overlaps a hook of KMRP's patch or of the controller patch, a byte KMRP's
    /// engine recipe writes, or a hook of D3M0's High FPS Fixes.
    ///
    /// A separate manifest from the Override one because these files live in the game
    /// folder rather than Override, and because the choice to install them is the user's
    /// and can differ between two installs of the same KMRP build.</summary>
    internal static class DriverCompatOperations
    {
        private sealed class InstalledFile
        {
            internal string Name;
            internal string Hash;
        }

        // Resource name -> file name in the game folder.
        private static readonly string[] ResourceNames = { "Kmrp.drivercompat.dinput8", "Kmrp.drivercompat.asi" };
        private static readonly string[] FileNames = { "dinput8.dll", "k1-modern-driver-compatibility.asi" };

        internal const string Version = "2.0.0";

        // What K1DC's two files import that Windows 7 does not have, from their import
        // tables (2.0.0, read 2026-10-19; everything else they import is Windows Vista's or
        // Windows 7's): dinput8.dll the first two, the .asi the other four. Windows will
        // not load a DLL whose imports it cannot find, and the game loads dinput8.dll as
        // it starts, so on such a PC K1DC would keep the game from starting at all. The
        // reporter of issue 41 met this with 1.0 on Windows 7. Asked of the PC rather than
        // of its version number, so Wine and Proton answer for themselves.
        // testing/regression/Test-DriverCompatImports.py fails when the vendored files
        // change, so that this list is read again then.
        private static readonly string[,] NewerImports =
        {
            { "kernel32.dll", "CreateFile2" },
            { "kernel32.dll", "GetSystemTimePreciseAsFileTime" },
            { "api-ms-win-core-synch-l1-2-0.dll", "WaitOnAddress" },
            { "api-ms-win-core-synch-l1-2-0.dll", "WakeByAddressAll" },
            { "api-ms-win-core-synch-l1-2-0.dll", "WakeByAddressSingle" },
            { "bcryptprimitives.dll", "ProcessPrng" },
        };

        // The installer tests: this function counts as missing, so that the path a
        // Windows 7 PC takes can be run on any PC.
        private const string MissingImportVariable = "KMRP_TEST_MISSING_IMPORT";

        private const uint LoadLibrarySearchSystem32 = 0x00000800;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr LoadLibraryEx(string name, IntPtr reserved, uint flags);

        [DllImport("kernel32.dll", CharSet = CharSet.Ansi, SetLastError = true)]
        private static extern IntPtr GetProcAddress(IntPtr module, string name);

        private static bool missingLooked;
        private static string missing;

        /// <summary>The first function K1DC needs that this PC lacks, as
        /// "CreateFile2 in kernel32.dll", or null when it has them all.</summary>
        internal static string MissingImport
        {
            get
            {
                if (missingLooked)
                    return missing;
                missingLooked = true;
                string pretend = Environment.GetEnvironmentVariable(MissingImportVariable);
                for (int i = 0; i < NewerImports.GetLength(0); i++)
                {
                    string library = NewerImports[i, 0], function = NewerImports[i, 1];
                    // From the system folder only, never the folder the installer was
                    // started from. A Windows 7 without update KB2533623 refuses the flag
                    // itself, which gives the same answer.
                    IntPtr module = LoadLibraryEx(library, IntPtr.Zero, LoadLibrarySearchSystem32);
                    if (module == IntPtr.Zero || GetProcAddress(module, function) == IntPtr.Zero ||
                        String.Equals(pretend, function, StringComparison.Ordinal))
                    {
                        missing = function + " in " + library;
                        break;
                    }
                }
                return missing;
            }
        }

        /// <summary>Whether K1DC can run on this PC: Windows 8 or later, or a Wine with
        /// the same functions.</summary>
        internal static bool CanRunHere
        {
            get { return MissingImport == null; }
        }

        // KMRP\driver-compat.manifest (KmrpFolder); KMRP_DriverCompat.manifest in the game
        // folder until 2026-10-20.
        private static string ManifestPath(string executablePath)
        {
            return KmrpFolder.PathOf(executablePath, KmrpFolder.DriverCompatManifest);
        }

        internal static bool Available
        {
            get
            {
                for (int i = 0; i < ResourceNames.Length; i++)
                    using (Stream stream = Assembly.GetExecutingAssembly()
                               .GetManifestResourceStream(ResourceNames[i]))
                        if (stream == null)
                            return false;
                return true;
            }
        }

        /// <summary>Write the loader and K1DC's payload into the game folder, unless
        /// something already occupies one of those names that we did not put there.
        ///
        /// Until 2026-09-29 the loader also installed on its own, with driver
        /// compatibility off, because KMRP's runtime was an .asi it loaded. KMRP's
        /// runtime is KOTOR Patch Manager's now, loaded by KPM's binkw32.dll proxy
        /// (KpmEditionOperations), so K1DC's two files install together or not at
        /// all.</summary>
        internal static void Install(string executablePath, Action<string> report)
        {
            if (!Available)
                return;
            if (!CanRunHere)
            {
                SafeReport(report, "Modern Driver Compatibility was not installed: it needs Windows 8 or " +
                    "later, and on this PC it would keep the game from starting (" + MissingImport + " is missing).");
                return;
            }
            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            List<InstalledFile> installed = new List<InstalledFile>();
            int count = FileNames.Length;

            for (int i = 0; i < count; i++)
            {
                string target = Path.Combine(folder, FileNames[i]);
                // Never clobber a file we did not write. A user may already run a
                // different ASI loader, or K1DC installed by hand, and silently replacing
                // either would be both destructive and undiagnosable.
                if (File.Exists(target) && !WasInstalledByUs(executablePath, FileNames[i], target))
                {
                    SafeReport(report, "Left the existing " + FileNames[i] +
                        " alone; the driver compatibility patch was not installed.");
                    return;
                }
            }

            for (int i = 0; i < count; i++)
            {
                string target = Path.Combine(folder, FileNames[i]);
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream(ResourceNames[i]))
                using (FileStream output = File.Create(target))
                    stream.CopyTo(output);
                InstalledFile record = new InstalledFile();
                record.Name = FileNames[i];
                record.Hash = GoldPatch.HashFile(target);
                installed.Add(record);
            }

            WriteManifest(executablePath, installed);
            SafeReport(report, "Installed K1 Modern Driver Compatibility " + Version +
                " (by Synchro). swkotor.exe was not modified.");
        }

        /// <summary>Remove both files, if we installed them and nothing has changed them
        /// since. Always safe to call: no manifest means nothing to do.</summary>
        internal static void Restore(string executablePath, Action<string> report)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return;

            string folder = Path.GetDirectoryName(Path.GetFullPath(executablePath));
            List<InstalledFile> records = ReadManifest(manifestPath);
            int removed = 0;
            int kept = 0;
            foreach (InstalledFile record in records)
            {
                string target = Path.Combine(folder, record.Name);
                if (!File.Exists(target))
                    continue;
                if (GoldPatch.HashFile(target) != record.Hash)
                {
                    // Changed since we wrote it -- upgraded by hand, most likely. Leave
                    // it, and say so, rather than deleting someone else's newer copy.
                    kept++;
                    continue;
                }
                File.Delete(target);
                removed++;
            }

            File.Delete(manifestPath);
            if (removed > 0)
                SafeReport(report, "Removed the bundled driver compatibility patch.");
            if (kept > 0)
                SafeReport(report, "Left " + kept +
                    " driver compatibility file(s) in place because they changed after install.");
        }

        private static bool WasInstalledByUs(string executablePath, string name, string target)
        {
            string manifestPath = ManifestPath(executablePath);
            if (!File.Exists(manifestPath))
                return false;
            foreach (InstalledFile record in ReadManifest(manifestPath))
                if (String.Equals(record.Name, name, StringComparison.OrdinalIgnoreCase))
                    return GoldPatch.HashFile(target) == record.Hash;
            return false;
        }

        private static void WriteManifest(string executablePath, List<InstalledFile> files)
        {
            StringBuilder text = new StringBuilder();
            text.Append("version\t").Append(Version).Append("\r\n");
            foreach (InstalledFile record in files)
                text.Append(record.Name).Append('\t').Append(record.Hash).Append("\r\n");
            File.WriteAllText(ManifestPath(executablePath), text.ToString(), new UTF8Encoding(false));
        }

        private static List<InstalledFile> ReadManifest(string manifestPath)
        {
            List<InstalledFile> records = new List<InstalledFile>();
            try
            {
                foreach (string line in File.ReadAllLines(manifestPath, Encoding.UTF8))
                {
                    string[] parts = line.Split('\t');
                    if (parts.Length != 2 || parts[0] == "version")
                        continue;
                    InstalledFile record = new InstalledFile();
                    record.Name = parts[0];
                    record.Hash = parts[1];
                    records.Add(record);
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
    }

    internal static class UiTheme
    {
        internal static readonly Color Window = Color.FromArgb(7, 12, 21);
        internal static readonly Color Panel = Color.FromArgb(20, 29, 40);
        internal static readonly Color PanelDeep = Color.FromArgb(7, 14, 23);
        internal static readonly Color PanelHover = Color.FromArgb(28, 49, 63);
        internal static readonly Color Border = Color.FromArgb(34, 103, 132);
        internal static readonly Color Accent = Color.FromArgb(42, 198, 239);
        internal static readonly Color AccentStrong = Color.FromArgb(0, 166, 214);
        internal static readonly Color AccentDark = Color.FromArgb(0, 83, 116);
        internal static readonly Color Gold = Color.FromArgb(226, 195, 92);
        internal static readonly Color Text = Color.FromArgb(236, 243, 248);
        internal static readonly Color TextMuted = Color.FromArgb(177, 195, 208);
        internal static readonly Color Success = Color.FromArgb(126, 224, 171);
        internal static readonly Color Warning = Color.FromArgb(255, 207, 112);
        internal static readonly Color Error = Color.FromArgb(255, 142, 142);
        internal static readonly Color Disabled = Color.FromArgb(47, 56, 67);
        internal static readonly Color DisabledText = Color.FromArgb(139, 151, 164);

        // Sampled off the reference: the surround is near-black navy, the card a step
        // lighter and bluer, and the glyph stroke a bright cornflower.
        internal static readonly Color Card = Color.FromArgb(13, 21, 34);
        internal static readonly Color CardHover = Color.FromArgb(19, 30, 47);
        internal static readonly Color CardEdge = Color.FromArgb(31, 46, 69);
        internal static readonly Color Hairline = Color.FromArgb(23, 34, 52);
        internal static readonly Color Badge = Color.FromArgb(18, 28, 44);
        internal static readonly Color BadgeEdge = Color.FromArgb(30, 45, 68);
        internal static readonly Color Field = Color.FromArgb(9, 15, 26);
        internal static readonly Color AccentLit = Color.FromArgb(96, 178, 255);
        internal static readonly Color TextFaint = Color.FromArgb(122, 138, 154);
        // Attribution ink. Desaturated silver-blue: readable against the card, clearly
        // secondary to Accent (42,198,239) so a credit never reads as a control.
        internal static readonly Color AuthorInk = Color.FromArgb(146, 170, 200);
        // The step glyphs get their own colour rather than reusing Accent, so retuning the
        // primary button never drags the icons with it.
        internal static readonly Color GlyphInk = Color.FromArgb(92, 165, 250);

        internal enum Glyph { Folder, Shield, Monitor, Tools }

        // Hand-drawn icons, when supplied. Each is stored as white ink on transparency, so
        // a colour matrix multiplies it straight to GlyphInk -- the colour stays one
        // constant here instead of being baked into the artwork. Steps without a supplied
        // icon fall back to DrawGlyph, so a partial set still builds and still looks whole.
        private static readonly Dictionary<Glyph, Image> IconArt = new Dictionary<Glyph, Image>();
        private static bool iconsLoaded;
        private static readonly Dictionary<string, Image> StatusArt = new Dictionary<string, Image>();
        // Icons rendered at the exact size they are drawn, keyed "name@WxH". Built once
        // and reused, because rescaling the source on every paint stalled the animation.
        private static readonly Dictionary<string, Bitmap> ScaledArt = new Dictionary<string, Bitmap>();
        // The opaque bounding box of each icon, so its transparent margin is not drawn.
        private static readonly Dictionary<string, Rectangle> InkBounds = new Dictionary<string, Rectangle>();

        private static Image IconFor(Glyph glyph)
        {
            if (!iconsLoaded)
            {
                iconsLoaded = true;
                string[] names = { "folder", "shield", "monitor", "tools" };
                Glyph[] keys = { Glyph.Folder, Glyph.Shield, Glyph.Monitor, Glyph.Tools };
                for (int i = 0; i < names.Length; i++)
                {
                    try
                    {
                        using (Stream stream = Assembly.GetExecutingAssembly()
                                   .GetManifestResourceStream("Kmrp.icon." + names[i]))
                            if (stream != null)
                                IconArt[keys[i]] = Image.FromStream(stream);
                    }
                    catch { }
                }
            }
            Image art;
            return IconArt.TryGetValue(glyph, out art) ? art : null;
        }

        /// <summary>Draws a supplied icon tinted to `color`, or returns false if there is
        /// none for this step.</summary>
        internal static bool DrawIconArt(Graphics g, Glyph glyph, Rectangle circle, Color color)
        {
            Image art = IconFor(glyph);
            if (art == null)
                return false;

            int side = (int)Math.Round(circle.Width * 0.563F);
            Rectangle box = new Rectangle(circle.X + (circle.Width - side) / 2,
                                          circle.Y + (circle.Height - side) / 2, side, side);
            using (ImageAttributes tint = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix(new float[][] {
                    new float[] { color.R / 255F, 0, 0, 0, 0 },
                    new float[] { 0, color.G / 255F, 0, 0, 0 },
                    new float[] { 0, 0, color.B / 255F, 0, 0 },
                    new float[] { 0, 0, 0, 1, 0 },
                    new float[] { 0, 0, 0, 0, 1 } });
                tint.SetColorMatrix(matrix);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(art, box, 0, 0, art.Width, art.Height, GraphicsUnit.Pixel, tint);
            }
            return true;
        }

        /// <summary>Draw the supplied verified-status badge, tinted with the semantic
        /// success colour. The caller keeps the icon and label optically grouped.</summary>
        /// <summary>Draws supplied artwork as a solid-colour silhouette taken from its
        /// alpha channel, cropped to its ink and pre-scaled.
        ///
        /// **Why the tint replaces rather than multiplies.** `DrawStatusArt` multiplies
        /// the source by the colour, which only works for white artwork -- and every icon
        /// that predates this one is white. The settings gear is black line art on
        /// transparency, and black times anything is black. This zeroes the source RGB and
        /// adds the wanted colour, keeping alpha, so the shape and its antialiasing come
        /// from the artwork and only the colour is ours. Equivalent to the multiply for
        /// white art, correct for any other.
        ///
        /// **Why it caches.** The source is 2000x2000 and is drawn into a ~35 px box.
        /// Resampling that on every paint with HighQualityBicubic cost enough to visibly
        /// stall the header animation while the pointer sat on the button -- hovering
        /// repaints, and each repaint was rescaling four million pixels. The scaled result
        /// is built once per size and reused, so a repaint is a 1:1 blit of a small bitmap.
        ///
        /// **Why it crops.** The artwork carries roughly 10-16% transparent margin on each
        /// side, so drawing it whole wasted a third of the space it was given. The opaque
        /// bounding box is measured once and only that region is drawn, fitted to the box
        /// with its aspect preserved and centred.</summary>
        internal static bool DrawIconMask(Graphics g, string name, Rectangle box, Color color)
        {
            if (box.Width <= 0 || box.Height <= 0)
                return false;
            Bitmap scaled = ScaledIcon(name, box.Width, box.Height);
            if (scaled == null)
                return false;

            using (ImageAttributes attributes = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix(new float[][] {
                    new float[] { 0, 0, 0, 0, 0 },
                    new float[] { 0, 0, 0, 0, 0 },
                    new float[] { 0, 0, 0, 0, 0 },
                    new float[] { 0, 0, 0, 1, 0 },
                    new float[] { color.R / 255F, color.G / 255F, color.B / 255F, 0, 1 } });
                attributes.SetColorMatrix(matrix);
                // 1:1, so no resampling happens here.
                g.DrawImage(scaled, box, 0, 0, scaled.Width, scaled.Height,
                            GraphicsUnit.Pixel, attributes);
            }
            return true;
        }

        /// <summary>The icon cropped to its ink and rendered at exactly this size, built
        /// once and cached. Returns null if the artwork was not shipped.</summary>
        private static Bitmap ScaledIcon(string name, int width, int height)
        {
            string key = name + "@" + width.ToString(CultureInfo.InvariantCulture)
                       + "x" + height.ToString(CultureInfo.InvariantCulture);
            Bitmap cached;
            if (ScaledArt.TryGetValue(key, out cached))
                return cached;

            Image source = LoadIcon(name);
            if (source == null)
            {
                ScaledArt[key] = null;
                return null;
            }

            Rectangle ink = InkBoundsOf(name, source);
            Bitmap target = new Bitmap(width, height, PixelFormat.Format32bppArgb);
            using (Graphics g = Graphics.FromImage(target))
            {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.CompositingQuality = CompositingQuality.HighQuality;

                // Fit the ink into the box, preserving its aspect and centring it.
                double scale = Math.Min(width / (double)ink.Width, height / (double)ink.Height);
                int drawWidth = Math.Max(1, (int)Math.Round(ink.Width * scale));
                int drawHeight = Math.Max(1, (int)Math.Round(ink.Height * scale));
                Rectangle destination = new Rectangle((width - drawWidth) / 2,
                                                      (height - drawHeight) / 2,
                                                      drawWidth, drawHeight);
                g.DrawImage(source, destination, ink.X, ink.Y, ink.Width, ink.Height,
                            GraphicsUnit.Pixel);
            }
            ScaledArt[key] = target;
            return target;
        }

        private static Image LoadIcon(string name)
        {
            Image art;
            if (StatusArt.TryGetValue(name, out art))
                return art;
            try
            {
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream("Kmrp.icon." + name))
                using (Image source = stream == null ? null : Image.FromStream(stream))
                    art = source == null ? null : new Bitmap(source);
            }
            catch { art = null; }
            StatusArt[name] = art;
            return art;
        }

        /// <summary>The smallest rectangle containing every pixel of the artwork that is
        /// not effectively transparent. Measured once per icon with LockBits -- per-pixel
        /// GetPixel over four million pixels takes long enough to be felt at startup.</summary>
        private static Rectangle InkBoundsOf(string name, Image source)
        {
            Rectangle bounds;
            if (InkBounds.TryGetValue(name, out bounds))
                return bounds;

            bounds = new Rectangle(0, 0, source.Width, source.Height);
            Bitmap bitmap = source as Bitmap;
            if (bitmap != null)
            {
                BitmapData data = null;
                try
                {
                    data = bitmap.LockBits(new Rectangle(0, 0, bitmap.Width, bitmap.Height),
                                           ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
                    int minX = bitmap.Width, minY = bitmap.Height, maxX = -1, maxY = -1;
                    // Marshal.Copy rather than a pointer walk: this project compiles
                    // without /unsafe, and one row at a time keeps the copy small.
                    byte[] row = new byte[Math.Abs(data.Stride)];
                    for (int y = 0; y < bitmap.Height; y++)
                    {
                        Marshal.Copy(new IntPtr(data.Scan0.ToInt64() + (long)y * data.Stride),
                                     row, 0, row.Length);
                        for (int x = 0; x < bitmap.Width; x++)
                        {
                            if (row[x * 4 + 3] <= 8)   // alpha, BGRA
                                continue;
                            if (x < minX) minX = x;
                            if (x > maxX) maxX = x;
                            if (y < minY) minY = y;
                            if (y > maxY) maxY = y;
                        }
                    }
                    if (maxX >= minX && maxY >= minY)
                        bounds = new Rectangle(minX, minY, maxX - minX + 1, maxY - minY + 1);
                }
                catch { }
                finally
                {
                    if (data != null)
                        bitmap.UnlockBits(data);
                }
            }
            InkBounds[name] = bounds;
            return bounds;
        }

        /// <summary>Draws a supplied status label -- "verified" or "missing" -- tinted to
        /// `color`, or returns false if that artwork was not shipped, in which case the
        /// state falls back to text alone.</summary>
        internal static bool DrawStatusArt(Graphics g, string name, Rectangle box, Color color)
        {
            Image art;
            if (!StatusArt.TryGetValue(name, out art))
            {
                try
                {
                    using (Stream stream = Assembly.GetExecutingAssembly()
                               .GetManifestResourceStream("Kmrp.icon." + name))
                    using (Image source = stream == null ? null : Image.FromStream(stream))
                        art = source == null ? null : new Bitmap(source);
                }
                catch { art = null; }
                StatusArt[name] = art;
            }
            if (art == null)
                return false;

            using (ImageAttributes tint = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix(new float[][] {
                    new float[] { color.R / 255F, 0, 0, 0, 0 },
                    new float[] { 0, color.G / 255F, 0, 0, 0 },
                    new float[] { 0, 0, color.B / 255F, 0, 0 },
                    new float[] { 0, 0, 0, 1, 0 },
                    new float[] { 0, 0, 0, 0, 1 } });
                tint.SetColorMatrix(matrix);
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.DrawImage(art, box, 0, 0, art.Width, art.Height, GraphicsUnit.Pixel, tint);
            }
            return true;
        }

        internal static GraphicsPath RoundedRect(Rectangle r, int radius)
        {
            int d = Math.Max(1, radius * 2);
            GraphicsPath path = new GraphicsPath();
            path.AddArc(r.X, r.Y, d, d, 180, 90);
            path.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            path.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            path.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            path.CloseFigure();
            return path;
        }

        /// <summary>Maps a point given in an icon's unit box onto its placed rectangle.</summary>
        private static PointF P(RectangleF b, float u, float v)
        {
            return new PointF(b.X + u * b.Width, b.Y + v * b.Height);
        }

        /// <summary>The icon's box inside a badge. Measured off the reference set: the ink
        /// spans 0.563 of the disc's diameter, and each glyph has its own aspect.</summary>
        private static RectangleF IconBox(Rectangle circle, float aspect)
        {
            float w = circle.Width * 0.563F;
            float h = w / aspect;
            return new RectangleF(circle.X + (circle.Width - w) / 2F,
                                  circle.Y + (circle.Height - h) / 2F, w, h);
        }

        /// <summary>Step icons, drawn rather than shipped, so the patcher stays a single
        /// file. Every coordinate below was measured off the reference artwork by scanning
        /// ink runs row by row and normalising to each glyph's own bounding box -- including
        /// the details that are easy to get wrong from memory, such as the monitor's stand
        /// being two neck strokes rather than one, and the shield being a peaked crest
        /// rather than a rounded dome.</summary>
        internal static void DrawGlyph(Graphics g, Glyph glyph, Rectangle circle, Color color)
        {
            float stroke = Math.Max(1.4F, circle.Width * 0.052F);
            using (Pen pen = new Pen(color, stroke))
            {
                pen.StartCap = LineCap.Round;
                pen.EndCap = LineCap.Round;
                pen.LineJoin = LineJoin.Round;

                if (glyph == Glyph.Folder)
                {
                    // 190x164 in the reference. A tab at the top left, a diagonal shoulder
                    // to the body's top edge at 0.20, a seam across the full width at 0.30,
                    // and an inner line at 0.80 spanning 0.24..0.86.
                    RectangleF b = IconBox(circle, 190F / 164F);
                    using (GraphicsPath back = new GraphicsPath())
                    {
                        back.AddLine(P(b, 0.02F, 0.34F), P(b, 0.02F, 0.10F));
                        back.AddLine(P(b, 0.02F, 0.10F), P(b, 0.07F, 0.02F));
                        back.AddLine(P(b, 0.07F, 0.02F), P(b, 0.35F, 0.02F));
                        back.AddLine(P(b, 0.35F, 0.02F), P(b, 0.46F, 0.19F));
                        back.AddLine(P(b, 0.46F, 0.19F), P(b, 0.94F, 0.19F));
                        back.AddLine(P(b, 0.94F, 0.19F), P(b, 0.98F, 0.26F));
                        g.DrawPath(pen, back);
                    }
                    using (GraphicsPath front = new GraphicsPath())
                    {
                        front.AddLine(P(b, 0.02F, 0.30F), P(b, 0.98F, 0.30F));
                        front.AddLine(P(b, 0.98F, 0.30F), P(b, 0.98F, 0.92F));
                        front.AddArc(b.X + 0.86F * b.Width, b.Y + 0.86F * b.Height,
                                     0.12F * b.Width, 0.13F * b.Height, 0, 90);
                        front.AddLine(P(b, 0.92F, 0.99F), P(b, 0.08F, 0.99F));
                        front.AddArc(b.X + 0.02F * b.Width, b.Y + 0.86F * b.Height,
                                     0.12F * b.Width, 0.13F * b.Height, 90, 90);
                        front.AddLine(P(b, 0.02F, 0.92F), P(b, 0.02F, 0.30F));
                        g.DrawPath(pen, front);
                    }
                    g.DrawLine(pen, P(b, 0.24F, 0.80F), P(b, 0.86F, 0.80F));
                }
                else if (glyph == Glyph.Shield)
                {
                    // 182x212 -- taller than wide, and peaked: a point at the top centre,
                    // shoulders sweeping out to the full width by 0.25, then curving in to a
                    // point at the bottom.
                    RectangleF b = IconBox(circle, 182F / 212F);
                    using (GraphicsPath shield = new GraphicsPath())
                    {
                        shield.AddLine(P(b, 0.50F, 0.01F), P(b, 0.04F, 0.22F));
                        shield.AddBezier(P(b, 0.04F, 0.22F), P(b, 0.04F, 0.52F),
                                         P(b, 0.18F, 0.84F), P(b, 0.50F, 0.99F));
                        shield.AddBezier(P(b, 0.50F, 0.99F), P(b, 0.82F, 0.84F),
                                         P(b, 0.96F, 0.52F), P(b, 0.96F, 0.22F));
                        shield.AddLine(P(b, 0.96F, 0.22F), P(b, 0.50F, 0.01F));
                        g.DrawPath(pen, shield);
                    }
                }
                else if (glyph == Glyph.Monitor)
                {
                    // 199x177. Screen to 0.78, then TWO neck strokes at 0.445 and 0.56
                    // running to 0.93, then a base bar spanning 0.23..0.76.
                    RectangleF b = IconBox(circle, 199F / 177F);
                    using (GraphicsPath screen = RoundedRect(
                               new Rectangle((int)(b.X + 0.02F * b.Width), (int)(b.Y + 0.02F * b.Height),
                                             (int)(0.96F * b.Width), (int)(0.76F * b.Height)),
                               (int)Math.Max(2F, 0.06F * b.Width)))
                        g.DrawPath(pen, screen);
                    // The reference puts the two neck struts at 0.445 and 0.560. At our icon
                    // size that is barely 4px apart and two round-capped strokes merge into
                    // one blob, losing the very detail that distinguishes this stand. Opened
                    // to 0.40/0.60 so both struts still read -- a deliberate departure from
                    // the measurement, because the measurement does not survive the scale.
                    g.DrawLine(pen, P(b, 0.40F, 0.78F), P(b, 0.40F, 0.93F));
                    g.DrawLine(pen, P(b, 0.60F, 0.78F), P(b, 0.60F, 0.93F));
                    g.DrawLine(pen, P(b, 0.23F, 0.97F), P(b, 0.76F, 0.97F));
                }
                else
                {
                    // 189x197. A screwdriver from the top left down to the bottom right,
                    // crossing a spanner whose open jaw is at the top right.
                    RectangleF b = IconBox(circle, 189F / 197F);
                    // Screwdriver: handle at the top left as a closed blade shape, shaft down
                    // to a tip at the bottom right.
                    using (GraphicsPath handle = new GraphicsPath())
                    {
                        handle.AddLine(P(b, 0.00F, 0.12F), P(b, 0.12F, 0.00F));
                        handle.AddLine(P(b, 0.12F, 0.00F), P(b, 0.38F, 0.22F));
                        handle.AddLine(P(b, 0.38F, 0.22F), P(b, 0.26F, 0.34F));
                        handle.CloseFigure();
                        g.DrawPath(pen, handle);
                    }
                    g.DrawLine(pen, P(b, 0.27F, 0.25F), P(b, 0.94F, 0.94F));
                    // Spanner: shaft from the bottom left up to an open jaw at the top right.
                    g.DrawLine(pen, P(b, 0.06F, 0.94F), P(b, 0.62F, 0.38F));
                    using (GraphicsPath jaw = new GraphicsPath())
                    {
                        // A narrower gap than a plain C: 80 degrees, opening up and to the
                        // right, away from the shaft, so it reads as a jaw and not a letter.
                        jaw.AddArc(b.X + 0.54F * b.Width, b.Y + 0.04F * b.Height,
                                   0.42F * b.Width, 0.42F * b.Height, 25, 280);
                        g.DrawPath(pen, jaw);
                    }
                }
            }
        }

        internal static Font DisplayFont(float size, FontStyle style)
        {
            try { return new Font("Bahnschrift SemiCondensed", size, style); }
            catch { return new Font("Segoe UI Semibold", size, style); }
        }

    }

    internal sealed class KotorProgressBar : Control
    {
        private int minimum;
        private int maximum = 100;
        private int currentValue;

        internal KotorProgressBar()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                ControlStyles.ResizeRedraw | ControlStyles.UserPaint, true);
            TabStop = false;
        }

        internal int Minimum
        {
            get { return minimum; }
            set { minimum = value; Value = currentValue; }
        }

        internal int Maximum
        {
            get { return maximum; }
            set { maximum = Math.Max(minimum + 1, value); Value = currentValue; }
        }

        internal int Value
        {
            get { return currentValue; }
            set
            {
                currentValue = Math.Max(minimum, Math.Min(maximum, value));
                Invalidate();
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            Rectangle track = ClientRectangle;
            if (track.Width <= 1 || track.Height <= 1)
                return;
            track.Width -= 1;
            track.Height -= 1;

            using (SolidBrush background = new SolidBrush(UiTheme.PanelDeep))
                e.Graphics.FillRectangle(background, track);
            using (Pen border = new Pen(UiTheme.Border))
                e.Graphics.DrawRectangle(border, track);

            double fraction = (double)(currentValue - minimum) / (maximum - minimum);
            int fillWidth = (int)Math.Round((track.Width - 2) * fraction);
            if (fillWidth <= 0)
                return;

            Rectangle fill = new Rectangle(track.Left + 1, track.Top + 1,
                fillWidth, Math.Max(1, track.Height - 1));
            using (SolidBrush energy = new SolidBrush(UiTheme.AccentStrong))
                e.Graphics.FillRectangle(energy, fill);

            if (fill.Width >= 4)
            {
                Rectangle tip = new Rectangle(fill.Right - 2, fill.Top, 2, fill.Height);
                using (SolidBrush highlight = new SolidBrush(UiTheme.Gold))
                    e.Graphics.FillRectangle(highlight, tip);
            }
        }
    }

    /// <summary>A rounded, faintly lit card. The whole UI sits on one of these.</summary>
    internal sealed class CardPanel : Panel
    {
        internal int Radius = 14;
        internal Color Fill = UiTheme.Card;
        internal Color Edge = UiTheme.CardEdge;
        internal float UiScale = 1F;

        internal CardPanel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = Color.Transparent;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            int scaledRadius = Math.Max(1, (int)Math.Round(Radius * UiScale));
            using (GraphicsPath path = UiTheme.RoundedRect(r, scaledRadius))
            using (SolidBrush fill = new SolidBrush(Fill))
            using (Pen edge = new Pen(Edge))
            {
                e.Graphics.FillPath(fill, path);
                e.Graphics.DrawPath(edge, path);
            }
        }
    }

    /// <summary>One numbered step: a lit glyph badge, a title, a subtitle, and room on
    /// the right for whatever that step needs (a button, a dropdown, a status word).</summary>
    internal sealed class StepRow : Panel
    {
        private bool dimmed;

        /// <summary>A step that is part of the flow but cannot be acted on yet. Drawn in
        /// muted ink so it reads as waiting rather than as available.</summary>
        internal bool Dimmed
        {
            get { return dimmed; }
            set
            {
                if (dimmed == value)
                    return;
                dimmed = value;
                Invalidate();
            }
        }

        internal const int HeaderHeight = 96;
        /// <summary>Room the card keeps between the last step and the action row. Step 2
        /// grew into it to offer "Get Editable EXE" and "Check Again" until 2026-09-30,
        /// when KMRP took Steam's and GOG's executables as they are; the space stays, so
        /// the window keeps its proportions, and the Mac's window copies them.</summary>
        internal const int ActionRoom = 67;
        internal const int ContentLeft = 120;
        internal string Title = String.Empty;
        internal string Subtitle = String.Empty;
        internal UiTheme.Glyph Icon = UiTheme.Glyph.Folder;
        internal bool DrawSeparator = true;
        internal float UiScale = 1F;

        internal StepRow()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = Color.Transparent;
            Height = HeaderHeight;
        }

        internal void SetSubtitle(string value)
        {
            if (Subtitle == value)
                return;
            Subtitle = value;
            Invalidate();
        }

        internal void SetTitle(string value)
        {
            if (Title == value)
                return;
            Title = value;
            Invalidate();
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            float scale = Math.Max(0.1F, UiScale);
            int horizontalInset = Math.Max(1, (int)Math.Round(26 * scale));

            if (DrawSeparator)
                using (Pen line = new Pen(UiTheme.Hairline, Math.Max(1F, scale)))
                    g.DrawLine(line, horizontalInset, Height - 1, Width - horizontalInset, Height - 1);

            // Anchored to the 96px header, whatever height the row is given.
            int headerHeight = Math.Min(Height, Math.Max(1, (int)Math.Round(HeaderHeight * scale)));
            int badge = Math.Max(1, (int)Math.Round(64 * scale));
            int badgeLeft = Math.Max(1, (int)Math.Round(28 * scale));
            int contentLeft = Math.Max(1, (int)Math.Round(ContentLeft * scale));
            Rectangle circle = new Rectangle(badgeLeft, (headerHeight - badge) / 2, badge, badge);
            using (SolidBrush disc = new SolidBrush(UiTheme.Badge))
                g.FillEllipse(disc, circle);
            using (Pen ring = new Pen(UiTheme.BadgeEdge))
                g.DrawEllipse(ring, circle);
            Color ink = dimmed ? UiTheme.TextFaint : UiTheme.GlyphInk;
            if (!UiTheme.DrawIconArt(g, Icon, circle, ink))
                UiTheme.DrawGlyph(g, Icon, circle, ink);

            using (SolidBrush text = new SolidBrush(dimmed ? UiTheme.TextFaint : UiTheme.Text))
            using (Font f = UiTheme.DisplayFont(22F * scale, FontStyle.Bold))
                g.DrawString(Title, f, text, contentLeft,
                    headerHeight / 2 - (int)Math.Round(30 * scale));
            using (SolidBrush text = new SolidBrush(dimmed ? UiTheme.TextFaint : UiTheme.TextMuted))
            using (Font f = new Font("Segoe UI", Math.Max(6F, 16.5F * scale)))
                g.DrawString(Subtitle, f, text, contentLeft,
                    headerHeight / 2 + (int)Math.Round(4 * scale));
        }
    }

    /// <summary>A right-aligned step status. Verified states can pair the supplied
    /// badge with their text as one compact unit instead of relying on a text glyph.</summary>
    internal sealed class StateLabel : Control
    {
        internal enum StatusBadge { None, Verified, Missing }

        internal float UiScale = 1F;
        private StatusBadge badge;

        internal StatusBadge Badge
        {
            get { return badge; }
            set
            {
                if (badge == value)
                    return;
                badge = value;
                Invalidate();
            }
        }

        internal StateLabel()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw |
                     ControlStyles.SupportsTransparentBackColor, true);
            BackColor = UiTheme.Card;
        }

        protected override void OnTextChanged(EventArgs e)
        {
            Invalidate();
            base.OnTextChanged(e);
        }

        protected override void OnForeColorChanged(EventArgs e)
        {
            Invalidate();
            base.OnForeColorChanged(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            TextFormatFlags flags = TextFormatFlags.SingleLine | TextFormatFlags.VerticalCenter |
                TextFormatFlags.NoPadding | TextFormatFlags.NoPrefix;
            Size textSize = TextRenderer.MeasureText(e.Graphics, Text, Font,
                new Size(Int32.MaxValue, Math.Max(1, Height)), flags);
            int textWidth = Math.Min(Width, textSize.Width);

            if (badge != StatusBadge.None)
            {
                // With no text the badge carries the state on its own, so it is drawn
                // larger and alone. The step's subtitle already says what is wrong.
                bool iconOnly = String.IsNullOrEmpty(Text);
                int iconSize = Math.Max(12, (int)Math.Round((iconOnly ? 48F : 32F) * UiScale));
                int gap = iconOnly ? 0 : Math.Max(4, (int)Math.Round(8 * UiScale));
                int groupWidth = Math.Min(Width, iconSize + gap + (iconOnly ? 0 : textWidth));
                int left = Math.Max(0, Width - groupWidth);
                Rectangle iconBox = new Rectangle(left, Math.Max(0, (Height - iconSize) / 2),
                    iconSize, iconSize);
                string art = badge == StatusBadge.Verified ? "verified" : "missing";
                if (UiTheme.DrawStatusArt(e.Graphics, art, iconBox, ForeColor))
                {
                    if (iconOnly)
                        return;
                    Rectangle textBox = new Rectangle(iconBox.Right + gap, 0,
                        Math.Max(1, Width - iconBox.Right - gap), Height);
                    TextRenderer.DrawText(e.Graphics, Text, Font, textBox, ForeColor,
                        flags | TextFormatFlags.Left);
                    return;
                }
            }

            TextRenderer.DrawText(e.Graphics, Text, Font, ClientRectangle, ForeColor,
                flags | TextFormatFlags.Right);
        }
    }

    /// <summary>Flat pill button. `Primary` gets the lit gradient, everything else the
    /// quiet outline used for Restore.</summary>
    internal sealed class PillButton : Control
    {
        internal bool Primary;
        /// <summary>A quieter secondary: a muted blue resting border instead of the card
        /// edge, and muted ink until hovered. For actions that sit under the primary one
        /// and must not compete with it.</summary>
        internal bool Subtle;
        /// <summary>Name of an embedded icon to draw centred instead of a label. The art
        /// is used as a silhouette, so it may be any colour -- see DrawIconMask.</summary>
        internal string IconName;
        internal float TextSize;
        internal float UiScale = 1F;
        private int progressPercent = -1;
        private bool hover;
        private bool down;

        /// <summary>-1 restores the normal button. Values from 0 through 100 draw
        /// a clipped, illuminated progress fill inside the existing button shell.</summary>
        internal int ProgressPercent
        {
            get { return progressPercent; }
            set
            {
                int clamped = value < 0 ? -1 : Math.Max(0, Math.Min(100, value));
                if (clamped == progressPercent)
                    return;
                progressPercent = clamped;
                Invalidate();
            }
        }

        internal PillButton()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor, true);
            // Opaque, not transparent. A transparent control inherits its parent's
            // background, which has not been painted yet while the window fades in, so
            // these appeared as white rectangles during the open animation. Every pill
            // sits on a Card-coloured surface, so this is what is behind it anyway.
            BackColor = UiTheme.Card;
            Cursor = Cursors.Hand;
            Height = 44;
        }

        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; down = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { down = true; Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { down = false; Invalidate(); base.OnMouseUp(e); }
        protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }
        protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            Rectangle r = new Rectangle(0, 0, Width - 1, Height - 1);
            float scale = Math.Max(0.1F, UiScale);
            bool progressActive = progressPercent >= 0;

            using (GraphicsPath path = UiTheme.RoundedRect(r,
                       Math.Max(1, (int)Math.Round(8 * scale))))
            {
                if (progressActive)
                {
                    using (LinearGradientBrush baseFill = new LinearGradientBrush(
                               new Rectangle(0, 0, Math.Max(1, Width), Math.Max(1, Height)),
                               UiTheme.AccentDark, Color.FromArgb(0, 112, 151), 90F))
                        g.FillPath(baseFill, path);

                    int filled = (int)Math.Round(Width * progressPercent / 100.0);
                    if (filled > 0)
                    {
                        GraphicsState state = g.Save();
                        g.SetClip(path);
                        Rectangle fillBox = new Rectangle(0, 0, Math.Max(1, filled), Height);
                        using (LinearGradientBrush fill = new LinearGradientBrush(fillBox,
                                   Color.FromArgb(116, 171, 193), Color.FromArgb(59, 132, 162), 90F))
                            g.FillRectangle(fill, fillBox);

                        int shineHeight = Math.Max(1, (int)Math.Round(Height * 0.48));
                        using (LinearGradientBrush shine = new LinearGradientBrush(
                                   new Rectangle(0, 0, Math.Max(1, filled), shineHeight),
                                   Color.FromArgb(34, 255, 255, 255),
                                   Color.FromArgb(0, 255, 255, 255), 90F))
                            g.FillRectangle(shine, 0, 0, filled, shineHeight);

                        if (filled < Width)
                        {
                            using (Pen leadingEdge = new Pen(Color.FromArgb(145, 170, 205, 220),
                                       Math.Max(1F, 1.4F * scale)))
                                g.DrawLine(leadingEdge, filled,
                                    Math.Max(3, (int)Math.Round(6 * scale)), filled,
                                    Height - Math.Max(3, (int)Math.Round(6 * scale)));
                        }
                        g.Restore(state);
                    }

                    using (Pen edge = new Pen(Color.FromArgb(105, 119, 177, 202),
                               Math.Max(1F, scale)))
                        g.DrawPath(edge, path);
                }
                else if (!Enabled)
                {
                    using (SolidBrush fill = new SolidBrush(UiTheme.Disabled))
                        g.FillPath(fill, path);
                }
                else if (Primary)
                {
                    Color top = down ? UiTheme.AccentDark : (hover ? UiTheme.AccentLit : UiTheme.Accent);
                    Color bottom = down ? UiTheme.AccentDark : UiTheme.AccentStrong;
                    using (LinearGradientBrush fill = new LinearGradientBrush(
                               new Rectangle(0, 0, Math.Max(1, Width), Math.Max(1, Height)), top, bottom, 90F))
                        g.FillPath(fill, path);
                }
                else
                {
                    using (SolidBrush fill = new SolidBrush(hover ? UiTheme.CardHover : UiTheme.Card))
                        g.FillPath(fill, path);
                    using (Pen edge = new Pen(hover ? UiTheme.Accent
                               : (Subtle ? UiTheme.Border : UiTheme.CardEdge)))
                        g.DrawPath(edge, path);
                }
            }

            Color ink = progressActive ? Color.White :
                (!Enabled ? UiTheme.DisabledText
                    : (Primary ? Color.White
                        : (Subtle && !hover ? UiTheme.TextMuted : UiTheme.Text)));

            if (!String.IsNullOrEmpty(IconName))
            {
                // Square icon buttons: the glyph is centred and sized against the shorter
                // side, so the button stays legible at any scale.
                int side = (int)Math.Round(Math.Min(Width, Height) * 0.74F);
                Rectangle iconBox = new Rectangle((Width - side) / 2, (Height - side) / 2,
                                                  Math.Max(1, side), Math.Max(1, side));
                UiTheme.DrawIconMask(g, IconName, iconBox, ink);
                return;
            }
            float baseTextSize = TextSize > 0F ? TextSize : (Primary ? 18F : 15.5F);
            using (StringFormat sf = new StringFormat())
            using (Font f = UiTheme.DisplayFont(Math.Max(6F, baseTextSize * scale), FontStyle.Bold))
            {
                sf.Alignment = StringAlignment.Center;
                sf.LineAlignment = StringAlignment.Center;
                if (progressActive)
                {
                    using (SolidBrush shadow = new SolidBrush(Color.FromArgb(115, 0, 39, 58)))
                        g.DrawString(Text, f, shadow,
                            new RectangleF(0, Math.Max(1F, scale), Width, Height), sf);
                }
                using (SolidBrush brush = new SolidBrush(ink))
                g.DrawString(Text, f, brush, new RectangleF(0, 0, Width, Height), sf);
            }
        }
    }

    /// <summary>ComboBox with the system's light border painted over, plus our own chevron.
    /// `FlatStyle.Flat` still draws a Windows border and drop button, so the only way to a
    /// dark field short of reimplementing selection is to repaint after WM_PAINT.</summary>
    internal sealed class DarkCombo : ComboBox
    {
        private const int WM_PAINT = 0x000F;
        internal float UiScale = 1F;

        internal DarkCombo()
        {
            DropDownStyle = ComboBoxStyle.DropDownList;
            FlatStyle = FlatStyle.Flat;
            DrawMode = DrawMode.OwnerDrawFixed;
            BackColor = UiTheme.Field;
            ForeColor = UiTheme.Text;
            ItemHeight = 30;
            IntegralHeight = false;
            DropDownHeight = 320;
        }

        internal void SetUiScale(float scale)
        {
            UiScale = Math.Max(0.1F, scale);
            ItemHeight = Math.Max(18, (int)Math.Round(30 * UiScale));
            DropDownHeight = Math.Max(ItemHeight * 4, (int)Math.Round(320 * UiScale));
            Invalidate();
        }

        protected override void WndProc(ref Message m)
        {
            base.WndProc(ref m);
            if (m.Msg != WM_PAINT)
                return;
            using (Graphics g = Graphics.FromHwnd(Handle))
            {
                g.SmoothingMode = SmoothingMode.AntiAlias;
                float scale = Math.Max(0.1F, UiScale);
                int button = Math.Max(18, (int)Math.Round(30 * scale));
                int buttonLeft = Math.Max(0, Width - button - 1);
                using (SolidBrush fill = new SolidBrush(UiTheme.Field))
                    g.FillRectangle(fill, buttonLeft, 0, Width - buttonLeft, Height);
                using (Pen edge = new Pen(UiTheme.CardEdge, Math.Max(1F, scale)))
                    g.DrawRectangle(edge, 0, 0, Width - 1, Height - 1);
                float cx = buttonLeft + (Width - buttonLeft) / 2F - scale;
                float cy = Height / 2F - scale;
                using (Pen chevron = new Pen(UiTheme.TextMuted, Math.Max(1F, 1.6F * scale)))
                {
                    chevron.StartCap = LineCap.Round;
                    chevron.EndCap = LineCap.Round;
                    g.DrawLines(chevron, new PointF[] {
                        new PointF(cx - 4.5F * scale, cy - 2F * scale),
                        new PointF(cx, cy + 2.5F * scale),
                        new PointF(cx + 4.5F * scale, cy - 2F * scale) });
                }
            }
        }
    }

    /// <summary>The header's plume, drawn with GDI+: the shared arithmetic is LightField.cs
    /// (split from here on 2026-10-30, unchanged); this half puts its emission buffer and its
    /// motes on the window.</summary>
    internal sealed partial class LightField : IDisposable
    {
        private Bitmap buffer;
        private Bitmap[] moteSprites;

        internal void Render(Graphics target, Rectangle area)
        {
            if (area.Width < 8 || area.Height < 8)
                return;
            long started = Stopwatch.GetTimestamp();
            if (!Compute(area.Width, area.Height))
                return;
            int w = width, h = height;
            if (buffer == null || buffer.Width != w || buffer.Height != h)
            {
                if (buffer != null)
                    buffer.Dispose();
                buffer = new Bitmap(w, h, PixelFormat.Format32bppArgb);
            }
            double freq = Stopwatch.Frequency / 1000.0;
            long t3 = Stopwatch.GetTimestamp();

            BitmapData data = buffer.LockBits(new Rectangle(0, 0, w, h),
                ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            Marshal.Copy(pixels, 0, data.Scan0, pixels.Length);
            buffer.UnlockBits(data);

            // HighQualityBilinear, counter-intuitively, is the fast path here. Plain
            // InterpolationMode.Bilinear was tried on the theory that the "high quality"
            // prefilter only matters when minifying: it made this stage six times slower,
            // 10.9 ms to 66.5 ms. GDI+ has an optimised implementation for the
            // HighQuality modes at this kind of magnification. Do not "optimise" it back.
            //
            // Only the rows that actually contain smoke are scaled. The plume occupies
            // roughly the top half of the header and the rest of the buffer is empty, so
            // blitting the whole thing spends most of its time magnifying zeroes.
            int rows = Math.Min(h, filledRows);
            InterpolationMode previous = target.InterpolationMode;
            target.InterpolationMode = InterpolationMode.HighQualityBilinear;
            if (rows > 0)
            {
                int destHeight = (int)Math.Ceiling(rows * area.Height / (double)h);
                if (destHeight > area.Height)
                    destHeight = area.Height;
                target.DrawImage(buffer,
                    new Rectangle(area.X, area.Y, area.Width, destHeight),
                    0, 0, w, rows, GraphicsUnit.Pixel);
            }
            target.InterpolationMode = previous;
            long t4 = Stopwatch.GetTimestamp();

            RenderMotes(target, area);
            long t5 = Stopwatch.GetTimestamp();

            msBlit = (t4 - t3) / freq;
            msMotes = (t5 - t4) / freq;

            lastRenderMs = (Stopwatch.GetTimestamp() - started) * 1000.0 / Stopwatch.Frequency;
        }

        /// <summary>Motes are drawn at full resolution, after the smoke buffer has been
        /// upscaled, so their size is independent of Downscale and they stay crisp
        /// against the soft plume. One cached sprite is tinted per mote through a reused
        /// colour matrix, so the pass allocates nothing.</summary>
        private void RenderMotes(Graphics target, Rectangle area)
        {
            if (moteSprites == null)
            {
                moteSprites = new Bitmap[MoteLevels];
                for (int i = 0; i < MoteLevels; i++)
                    moteSprites[i] = BuildMote(48, (i + 1) / (float)MoteLevels);
            }

            InterpolationMode previous = target.InterpolationMode;
            target.InterpolationMode = InterpolationMode.Bilinear;
            for (int i = 0; i < MoteCount; i++)
            {
                float mx, my, radiusOfHeight;
                int level;
                if (!MoteAt(i, out mx, out my, out radiusOfHeight, out level))
                    continue;
                float radius = radiusOfHeight * area.Height;
                float cx = area.Left + mx * area.Width;
                float cy = area.Top + my * area.Height;
                Rectangle dest = new Rectangle(
                    (int)(cx - radius), (int)(cy - radius),
                    Math.Max(2, (int)(radius * 2)), Math.Max(2, (int)(radius * 2)));
                target.DrawImage(moteSprites[level], dest);
            }
            target.InterpolationMode = previous;
        }

        private static Bitmap BuildMote(int size, float level)
        {
            Bitmap bitmap = new Bitmap(size, size, PixelFormat.Format32bppArgb);
            BitmapData data = bitmap.LockBits(new Rectangle(0, 0, size, size),
                ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            byte[] px = MotePixels(size, level);
            for (int y = 0; y < size; y++)
                Marshal.Copy(px, y * size * 4, new IntPtr(data.Scan0.ToInt64() + (long)y * data.Stride), size * 4);
            bitmap.UnlockBits(data);
            return bitmap;
        }

        public void Dispose()
        {
            if (buffer != null)
            {
                buffer.Dispose();
                buffer = null;
            }
            if (moteSprites != null)
            {
                for (int i = 0; i < moteSprites.Length; i++)
                    if (moteSprites[i] != null)
                        moteSprites[i].Dispose();
                moteSprites = null;
            }
        }
    }

    /// <summary>"KMRP 1.6.0 is available." Download opens the Deadly Stream page and
    /// Skip version closes. The switch, "Don't remind me again for 1.6.0", keeps that
    /// one version from being offered again, whichever button closes the dialog; a
    /// later version is still offered. There is deliberately no way to turn reminders
    /// off for good.
    ///
    /// The first design (2026-09-25) had a Skip button and a switch titled only
    /// "Don't remind me again", with "Not for 1.6.0; later versions will still show"
    /// beneath it. The maintainer found it unintuitive: the version belongs in the
    /// switch's own words.</summary>
    internal sealed class UpdateDialog : Form
    {
        private readonly OptionToggle remind;

        /// <summary>The switch. The dialog's own result is OK for Download and Cancel
        /// for Skip version, Escape or the close box.</summary>
        internal bool DontRemind { get { return remind.Checked; } }

        /// <summary>`scale` is the main window's, so the dialog matches it on any
        /// monitor; the numbers below are its 1080p design.</summary>
        internal UpdateDialog(string latest, string current, float scale)
        {
            this.scale = Math.Max(0.35F, scale);
            Text = "KMRP update";
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.CenterParent;
            BackColor = UiTheme.Card;
            Font = new Font("Segoe UI", Points(11F));
            ClientSize = new Size(Px(680), Px(292));
            KeyPreview = true;
            HandleCreated += delegate { MainForm.UseDarkTitleBar(Handle); };

            Label title = new Label();
            title.Text = "KMRP " + latest + " is available";
            title.Font = new Font("Segoe UI Semibold", Points(20F));
            title.ForeColor = UiTheme.Text;
            title.BackColor = UiTheme.Card;
            title.SetBounds(Px(32), Px(26), Px(616), Px(42));
            Controls.Add(title);

            Label body = new Label();
            body.Text = "You have " + current + ". The new version is on Deadly Stream.";
            body.Font = new Font("Segoe UI", Points(13F));
            body.ForeColor = UiTheme.TextMuted;
            body.BackColor = UiTheme.Card;
            body.SetBounds(Px(32), Px(72), Px(616), Px(30));
            Controls.Add(body);

            remind = new OptionToggle();
            remind.UiScale = this.scale;
            remind.Checked = false;
            remind.Title = "Don't remind me again for " + latest;
            // Title only: one line, centred on the switch.
            remind.SetBounds(Px(32), Px(118), Px(616), Px(60));
            Controls.Add(remind);

            PillButton download = new PillButton();
            download.UiScale = this.scale;
            download.Primary = true;
            download.TextSize = 17F;
            download.Text = "Download";
            download.SetBounds(Px(32), Px(206), Px(300), Px(56));
            download.Click += delegate { DialogResult = DialogResult.OK; Close(); };
            Controls.Add(download);

            PillButton skip = new PillButton();
            skip.UiScale = this.scale;
            skip.TextSize = 17F;
            skip.Text = "Skip version";
            skip.SetBounds(Px(348), Px(206), Px(300), Px(56));
            skip.Click += delegate { DialogResult = DialogResult.Cancel; Close(); };
            Controls.Add(skip);
        }

        private readonly float scale;
        private int Px(int design) { return Math.Max(1, (int)Math.Round(design * scale)); }
        private float Points(float design) { return Math.Max(6F, design * scale); }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.Escape)
            {
                DialogResult = DialogResult.Cancel;
                Close();
                return;
            }
            base.OnKeyDown(e);
        }
    }

    /// <summary>Step 3: nothing is chosen. KMRP's patch carries every resolution's
    /// files and the game lists the sizes the connected display reports, whatever
    /// display that is later: on a 4K television it lists that television's sizes. The
    /// game starts at the display's current size, written to swkotor.ini.
    ///
    /// From 2026-10-04 to 2026-10-07 step 3 had a "Choose" button and a checklist
    /// (ResolutionsDialog, CustomSizeDialog), saved as resolutionsOff and
    /// resolutionsExtra in KMRP's settings and written beside the game as
    /// kmrp-resolutions.txt. The maintainer had the choice removed on 2026-10-07; a
    /// kmrp-resolutions.txt of an earlier install is removed with that install and
    /// the patch's module no longer reads one.</summary>
    internal static class ResolutionSelection
    {
        // The rule is the core's (ResolutionCatalog.Covers, InstallCore.cs), which the Linux
        // installer uses too; here since 2026-10-30.
        internal static bool Covered(int width, int height)
        {
            return ResolutionCatalog.Covers(width, height);
        }

        /// <summary>The primary display's current size, or null.</summary>
        internal static int[] CurrentSize()
        {
            try
            {
                MainForm.DisplayMode mode = new MainForm.DisplayMode();
                mode.StructSize = (short)Marshal.SizeOf(typeof(MainForm.DisplayMode));
                if (MainForm.EnumDisplaySettings(null, MainForm.EnumCurrentSettings, ref mode))
                    return new[] { mode.PelsWidth, mode.PelsHeight };
            }
            catch { }
            return null;
        }

        /// <summary>The highest refresh rate the primary display reports at its current
        /// size, in hertz, or 0 when it cannot be told. What High FPS Fix's default goes
        /// by (KmrpSettings.HighFpsFix): a display that can run above 60 is one the game
        /// can run above 60 frames a second on.</summary>
        internal static int HighestRefresh()
        {
            return HighestRefresh(CurrentSize());
        }

        /// <summary>The same at a given size, {width, height}; at the display's current
        /// size when null.</summary>
        internal static int HighestRefresh(int[] current)
        {
            int highest = 0;
            try
            {
                MainForm.DisplayMode mode = new MainForm.DisplayMode();
                mode.StructSize = (short)Marshal.SizeOf(typeof(MainForm.DisplayMode));
                for (int i = 0; MainForm.EnumDisplaySettings(null, i, ref mode); i++)
                {
                    if (mode.BitsPerPel != 32 ||
                        (current != null && (mode.PelsWidth != current[0] || mode.PelsHeight != current[1])))
                        continue;
                    if (mode.DisplayFrequency > highest)
                        highest = mode.DisplayFrequency;
                }
                if (MainForm.EnumDisplaySettings(null, MainForm.EnumCurrentSettings, ref mode) &&
                    mode.DisplayFrequency > highest)
                    highest = mode.DisplayFrequency;
            }
            catch { }
            return highest;
        }

        /// <summary>The sizes the game lists for this display, that KMRP has a layout
        /// for: 32-bit modes of 60 Hz or more, as the game's own list filters them,
        /// each size once, as {width, height}.</summary>
        internal static List<int[]> DisplaySizes()
        {
            List<int[]> sizes = new List<int[]>();
            try
            {
                MainForm.DisplayMode mode = new MainForm.DisplayMode();
                mode.StructSize = (short)Marshal.SizeOf(typeof(MainForm.DisplayMode));
                for (int i = 0; MainForm.EnumDisplaySettings(null, i, ref mode); i++)
                {
                    int width = mode.PelsWidth, height = mode.PelsHeight;
                    if (mode.BitsPerPel != 32 || mode.DisplayFrequency < 60 ||
                        sizes.Exists(s => s[0] == width && s[1] == height) || !Covered(width, height))
                        continue;
                    sizes.Add(new[] { width, height });
                }
            }
            catch { }
            return sizes;
        }

        /// <summary>Where swkotor.ini starts the game: the display's current size when
        /// the game lists it, otherwise the largest of the display's sizes; null when
        /// the display reports none KMRP has a layout for.</summary>
        internal static int[] Start()
        {
            List<int[]> sizes = DisplaySizes();
            int[] current = CurrentSize();
            if (current != null && sizes.Exists(s => s[0] == current[0] && s[1] == current[1]))
                return current;
            int[] largest = null;
            foreach (int[] size in sizes)
                if (largest == null || (long)size[0] * size[1] > (long)largest[0] * largest[1])
                    largest = size;
            return largest;
        }

        /// <summary>Step 3's line under its title.</summary>
        internal static string Summary()
        {
            int[] start = Start();
            if (start == null)
                return "This display reports no resolution KMRP can use.";
            // One line: the step's row does not wrap.
            return "Starts at " + start[0].ToString(CultureInfo.InvariantCulture) + " × " +
                start[1].ToString(CultureInfo.InvariantCulture) + ". The game lists every resolution the connected display supports.";
        }
    }

    /// <summary>One switchable option: a title, a paragraph of explanation, and a pill
    /// switch on the right. Painted rather than a CheckBox so it carries the same ink and
    /// radius as the rest of the card.</summary>
    internal sealed class OptionToggle : Control
    {
        private bool hover;
        private bool isChecked = true;
        internal float UiScale = 1F;
        internal string Title = "";
        internal string Detail = "";
        /// <summary>Who wrote the component. Set right of the title, never folded into
        /// the description.</summary>
        internal string Author = "";
        /// <summary>A short fact about this PC, in green beside the title: "Display
        /// supports 120 Hz" on the High FPS Fix tile. Empty for none.</summary>
        internal string Note = "";
        /// <summary>The note's colour: green for a fact in the option's favour, amber
        /// (UiTheme.Warning) for the reason a disabled tile cannot be turned on.</summary>
        internal Color NoteColor = UiTheme.Success;
        internal event EventHandler CheckedChanged;

        internal bool Checked
        {
            get { return isChecked; }
            set
            {
                if (isChecked == value)
                    return;
                isChecked = value;
                Invalidate();
                if (CheckedChanged != null)
                    CheckedChanged(this, EventArgs.Empty);
            }
        }

        internal OptionToggle()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = UiTheme.Card;
            Cursor = Cursors.Hand;
            TabStop = false;
        }

        protected override void OnMouseEnter(EventArgs e) { hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { hover = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnClick(EventArgs e) { Checked = !Checked; base.OnClick(e); }
        // Disabled where the option cannot run on this PC (Modern Driver Compatibility on
        // Windows 7): the switch is drawn dim and the hand cursor goes.
        protected override void OnEnabledChanged(EventArgs e)
        {
            Cursor = Enabled ? Cursors.Hand : Cursors.Default;
            Invalidate();
            base.OnEnabledChanged(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;
            float scale = Math.Max(0.1F, UiScale);
            int radius = Math.Max(1, (int)Math.Round(10 * scale));
            Rectangle body = new Rectangle(0, 0, Width - 1, Height - 1);
            using (GraphicsPath path = UiTheme.RoundedRect(body, radius))
            {
                using (SolidBrush fill = new SolidBrush(hover ? UiTheme.CardHover : UiTheme.Badge))
                    g.FillPath(fill, path);
                using (Pen edge = new Pen(hover ? UiTheme.Border : UiTheme.CardEdge))
                    g.DrawPath(edge, path);
            }

            // A tile since 2026-10-09 (a full-width row until then; the maintainer asked
            // for tiles once there were six): the title on top, over as many lines as it
            // needs, the description under it, and along the bottom the credit on the
            // left and the switch on the right. The description has what is left
            // between the two and ends in an ellipsis where that is not enough.
            int pad = Math.Max(1, (int)Math.Round(16 * scale));
            int switchWidth = Math.Max(8, (int)Math.Round(64 * scale));
            int switchHeight = Math.Max(6, (int)Math.Round(32 * scale));
            int textWidth = Math.Max(1, Width - 2 * pad);
            int switchLeft = Width - pad - switchWidth;
            Rectangle track = new Rectangle(switchLeft, Height - pad - switchHeight, switchWidth, switchHeight);

            using (Font titleFont = new Font("Segoe UI Semibold", Math.Max(6F, 16F * scale)))
            using (Font authorFont = new Font("Segoe UI", Math.Max(6F, 13F * scale)))
            using (Font detailFont = new Font("Segoe UI", Math.Max(6F, 13F * scale)))
            using (SolidBrush titleInk = new SolidBrush(UiTheme.Text))
            using (SolidBrush authorInk = new SolidBrush(UiTheme.AuthorInk))
            using (SolidBrush detailInk = new SolidBrush(UiTheme.TextMuted))
            using (StringFormat wrap = new StringFormat())
            using (StringFormat credit = new StringFormat())
            {
                wrap.Trimming = StringTrimming.EllipsisWord;
                credit.LineAlignment = StringAlignment.Center;
                credit.FormatFlags = StringFormatFlags.NoWrap;
                credit.Trimming = StringTrimming.EllipsisCharacter;

                float lineHeight = titleFont.GetHeight(g);
                float titleTop = pad * 0.75F;
                // The note, where there is one, ends the title's first line on the right,
                // centred on that line, and the title keeps clear of it.
                int titleWidth = textWidth;
                if (!String.IsNullOrEmpty(Note))
                {
                    using (SolidBrush noteInk = new SolidBrush(NoteColor))
                    using (StringFormat right = new StringFormat())
                    {
                        right.Alignment = StringAlignment.Far;
                        right.LineAlignment = StringAlignment.Center;
                        right.FormatFlags = StringFormatFlags.NoWrap;
                        int noteWidth = (int)Math.Ceiling(g.MeasureString(Note, authorFont).Width);
                        g.DrawString(Note, authorFont, noteInk,
                            new RectangleF(pad, titleTop, textWidth, lineHeight), right);
                        titleWidth = Math.Max(1, textWidth - noteWidth - Math.Max(1, (int)Math.Round(8 * scale)));
                    }
                }
                float titleHeight = Math.Min(2 * lineHeight + 1,
                    (float)Math.Ceiling(g.MeasureString(Title, titleFont, titleWidth, wrap).Height));
                g.DrawString(Title, titleFont, titleInk, new RectangleF(pad, titleTop, titleWidth, titleHeight), wrap);

                float detailTop = titleTop + titleHeight + Math.Max(1, 3 * scale);
                float detailLine = detailFont.GetHeight(g);
                // Whole lines only, so no line is cut through its middle.
                float room = track.Top - Math.Max(1, 4 * scale) - detailTop;
                int lines = Math.Max(1, (int)Math.Floor(room / detailLine));
                g.DrawString(Detail, detailFont, detailInk,
                    new RectangleF(pad, detailTop, textWidth, lines * detailLine + 1), wrap);

                if (!String.IsNullOrEmpty(Author))
                    g.DrawString("by " + Author, authorFont, authorInk, new RectangleF(
                        pad, track.Top, Math.Max(1, switchLeft - pad - Math.Max(1, 8 * scale)), switchHeight), credit);
            }

            bool lit = isChecked && Enabled;
            using (GraphicsPath path = UiTheme.RoundedRect(track, switchHeight / 2))
            {
                using (SolidBrush fill = new SolidBrush(lit ? UiTheme.AccentStrong : UiTheme.Disabled))
                    g.FillPath(fill, path);
                using (Pen edge = new Pen(lit ? UiTheme.Accent : UiTheme.CardEdge))
                    g.DrawPath(edge, path);
            }
            // The knob is white in both states, as on iOS: the state is carried by the
            // track -- blue when on, grey when off -- and a white knob stays legible on
            // either without becoming a second colour to decode.
            int knob = switchHeight - Math.Max(2, (int)Math.Round(8 * scale));
            int knobX = isChecked ? track.Right - knob - (switchHeight - knob) / 2
                                  : track.Left + (switchHeight - knob) / 2;
            using (SolidBrush knobInk = new SolidBrush(!Enabled ? UiTheme.TextFaint : isChecked ? Color.White : UiTheme.TextMuted))
                g.FillEllipse(knobInk, knobX, track.Y + (switchHeight - knob) / 2, knob, knob);
        }
    }

    /// <summary>The scrolled part of a page (Advanced Settings since 2026-10-19, when a
    /// seventh tile came: the tiles keep the size six had, two rows in view). Its
    /// children are laid out as if nothing were scrolled; this panel is shifted up by
    /// the scroll.
    ///
    /// The window places every control from its design bounds whenever it is resized
    /// (MainForm.ApplyControlScale), which would put this back at the top. So the scroll
    /// is kept as a fraction of the distance there is to scroll, and every placement of
    /// this panel is shifted by that fraction of the distance at the new size.</summary>
    internal sealed class ScrollContent : Panel
    {
        private float fraction;
        private int layoutTop;   // where the window's layout puts it, unscrolled

        internal ScrollContent()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint, true);
            BackColor = UiTheme.Card;
        }

        /// <summary>How far it is scrolled: 0 at the top, 1 at the bottom.</summary>
        internal float Fraction
        {
            get { return fraction; }
            set
            {
                float next = Math.Max(0F, Math.Min(1F, value));
                if (Math.Abs(next - fraction) < 0.0001F)
                    return;
                fraction = next;
                base.SetBoundsCore(Left, layoutTop - RangeAt(Height), Width, Height, BoundsSpecified.Location);
            }
        }

        /// <summary>The distance it can be scrolled, in pixels: its height less the
        /// viewport's.</summary>
        internal int Range
        {
            get { return Parent == null ? 0 : Math.Max(0, Height - Parent.ClientSize.Height); }
        }

        private int RangeAt(int height)
        {
            int range = Parent == null ? 0 : Math.Max(0, height - Parent.ClientSize.Height);
            return (int)Math.Round(fraction * range);
        }

        protected override void SetBoundsCore(int x, int y, int width, int height, BoundsSpecified specified)
        {
            if ((specified & BoundsSpecified.Y) != 0)
                layoutTop = y;
            base.SetBoundsCore(x, layoutTop - RangeAt(height), width, height, specified | BoundsSpecified.Y);
        }
    }

    /// <summary>The window onto a ScrollContent: it clips it and eases it to where the
    /// scrollbar or the wheel sends it.</summary>
    internal sealed class ScrollViewport : Panel
    {
        internal readonly ScrollContent Content = new ScrollContent();
        internal float UiScale = 1F;
        /// <summary>What an arrow press or a wheel notch scrolls, at design size: a row
        /// of tiles and the gap under it.</summary>
        internal int DesignStep = 100;
        internal event EventHandler Scrolled;
        private readonly Timer ease = new Timer();
        private float target;

        internal ScrollViewport()
        {
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint, true);
            BackColor = UiTheme.Card;
            Controls.Add(Content);
            ease.Interval = 15;
            ease.Tick += delegate { Ease(); };
        }

        internal float Fraction { get { return Content.Fraction; } }
        internal int Range { get { return Content.Range; } }
        internal int StepPixels { get { return Math.Max(1, (int)Math.Round(DesignStep * UiScale)); } }

        /// <summary>How much of the content is in view, 0 to 1.</summary>
        internal float InView
        {
            get
            {
                return Content.Height <= 0 ? 1F : Math.Min(1F, ClientSize.Height / (float)Content.Height);
            }
        }

        /// <summary>Scrolls to `fraction`: at once, or eased over a few frames.</summary>
        internal void ScrollTo(float fraction, bool now)
        {
            target = Math.Max(0F, Math.Min(1F, fraction));
            if (now)
            {
                ease.Stop();
                Apply(target);
            }
            else if (!ease.Enabled)
                ease.Start();
        }

        /// <summary>Scrolls by `pixels` at the current size, from where it is heading.</summary>
        internal void ScrollBy(int pixels)
        {
            int range = Range;
            if (range > 0)
                ScrollTo(target + pixels / (float)range, false);
        }

        /// <summary>A WM_MOUSEWHEEL delta: 120 a notch, positive away from the player.</summary>
        internal void Wheel(int delta)
        {
            ScrollBy(-delta * StepPixels / 120);
        }

        private void Ease()
        {
            float current = Content.Fraction;
            float next = current + (target - current) * 0.35F;
            if (Math.Abs(target - next) * Math.Max(1, Range) < 0.5F)
            {
                next = target;
                ease.Stop();
            }
            Apply(next);
        }

        private void Apply(float fraction)
        {
            Content.Fraction = fraction;
            if (Scrolled != null)
                Scrolled(this, EventArgs.Empty);
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
                ease.Dispose();
            base.Dispose(disposing);
        }
    }

    /// <summary>A ScrollViewport's scrollbar, after KOTOR's own list scrollbars: an arrow
    /// box at each end, a thin rail between them, and a framed thumb with cut corners and
    /// a three-line grip, in the installer's blues (2026-10-19, the maintainer: "a
    /// fitting look inspired by kotor"). The arrows step a row and repeat while held,
    /// the rail pages, the thumb drags, and the wheel works anywhere over the page
    /// (MainForm.WheelOverSettings). Draws nothing while everything is in view.</summary>
    internal sealed class KotorScrollBar : Control
    {
        private enum Part { None, Up, Down, Thumb, Above, Below }

        private readonly ScrollViewport viewport;
        private readonly Timer repeat = new Timer();
        private Part hover;
        private Part pressed;
        private int dragFrom;
        private float dragFraction;

        internal KotorScrollBar(ScrollViewport viewport)
        {
            this.viewport = viewport;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint | ControlStyles.ResizeRedraw, true);
            BackColor = UiTheme.Card;
            TabStop = false;
            viewport.Scrolled += delegate { Invalidate(); };
            viewport.Content.SizeChanged += delegate { Invalidate(); };
            repeat.Tick += delegate
            {
                repeat.Interval = 70;
                Act(pressed);
            };
        }

        // The arrow boxes are square, as wide as the bar.
        private Rectangle UpBox { get { return new Rectangle(0, 0, Width, Width); } }
        private Rectangle DownBox { get { return new Rectangle(0, Height - Width, Width, Width); } }

        private Rectangle Rail
        {
            get
            {
                int gap = Math.Max(2, Width / 3);
                return Rectangle.FromLTRB(0, Width + gap, Width, Math.Max(Width + gap, Height - Width - gap));
            }
        }

        private Rectangle Thumb
        {
            get
            {
                Rectangle rail = Rail;
                int length = Math.Min(rail.Height, Math.Max(Width * 2, (int)Math.Round(rail.Height * viewport.InView)));
                int top = rail.Top + (int)Math.Round((rail.Height - length) * viewport.Fraction);
                return new Rectangle(0, top, Width, length);
            }
        }

        private Part HitTest(Point p)
        {
            if (viewport.Range <= 0)
                return Part.None;
            if (UpBox.Contains(p))
                return Part.Up;
            if (DownBox.Contains(p))
                return Part.Down;
            Rectangle thumb = Thumb;
            if (thumb.Contains(p))
                return Part.Thumb;
            if (Rail.Contains(p))
                return p.Y < thumb.Top ? Part.Above : Part.Below;
            return Part.None;
        }

        private void Act(Part part)
        {
            if (part == Part.Up)
                viewport.ScrollBy(-viewport.StepPixels);
            else if (part == Part.Down)
                viewport.ScrollBy(viewport.StepPixels);
            else if (part == Part.Above)
                viewport.ScrollBy(-viewport.ClientSize.Height);
            else if (part == Part.Below)
                viewport.ScrollBy(viewport.ClientSize.Height);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            base.OnMouseDown(e);
            if (e.Button != MouseButtons.Left)
                return;
            pressed = HitTest(e.Location);
            if (pressed == Part.Thumb)
            {
                dragFrom = e.Y;
                dragFraction = viewport.Fraction;
            }
            else if (pressed != Part.None)
            {
                Act(pressed);
                repeat.Interval = 400;
                repeat.Start();
            }
            Invalidate();
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            base.OnMouseMove(e);
            if (pressed == Part.Thumb)
            {
                int travel = Rail.Height - Thumb.Height;
                if (travel > 0)
                    viewport.ScrollTo(dragFraction + (e.Y - dragFrom) / (float)travel, true);
                return;
            }
            Part now = HitTest(e.Location);
            if (now != hover)
            {
                hover = now;
                Invalidate();
            }
        }

        protected override void OnMouseUp(MouseEventArgs e)
        {
            base.OnMouseUp(e);
            pressed = Part.None;
            repeat.Stop();
            hover = HitTest(e.Location);
            Invalidate();
        }

        protected override void OnMouseLeave(EventArgs e)
        {
            base.OnMouseLeave(e);
            hover = Part.None;
            Invalidate();
        }

        /// <summary>A rectangle with its corners cut, as KOTOR frames its buttons.</summary>
        private static GraphicsPath Chamfered(RectangleF r, float cut)
        {
            GraphicsPath path = new GraphicsPath();
            path.AddLines(new[]
            {
                new PointF(r.Left + cut, r.Top), new PointF(r.Right - cut, r.Top),
                new PointF(r.Right, r.Top + cut), new PointF(r.Right, r.Bottom - cut),
                new PointF(r.Right - cut, r.Bottom), new PointF(r.Left + cut, r.Bottom),
                new PointF(r.Left, r.Bottom - cut), new PointF(r.Left, r.Top + cut),
            });
            path.CloseFigure();
            return path;
        }

        private void DrawArrowBox(Graphics g, Rectangle box, bool up, Part part)
        {
            bool down = pressed == part;
            bool lit = hover == part || down;
            RectangleF r = new RectangleF(box.X + 0.5F, box.Y + 0.5F, box.Width - 1F, box.Height - 1F);
            float cut = Math.Max(1.5F, box.Width / 4F);
            using (GraphicsPath frame = Chamfered(r, cut))
            using (SolidBrush fill = new SolidBrush(down ? UiTheme.AccentDark : lit ? UiTheme.PanelHover : UiTheme.PanelDeep))
            using (Pen edge = new Pen(down ? UiTheme.Accent : lit ? UiTheme.AccentStrong : UiTheme.Border))
            {
                g.FillPath(fill, frame);
                g.DrawPath(edge, frame);
            }
            float inset = box.Width * 0.3F;
            float cx = box.X + box.Width / 2F;
            float topY = box.Y + inset;
            float bottomY = box.Bottom - inset;
            PointF[] triangle = up
                ? new[] { new PointF(cx, topY), new PointF(box.Right - inset, bottomY), new PointF(box.X + inset, bottomY) }
                : new[] { new PointF(box.X + inset, topY), new PointF(box.Right - inset, topY), new PointF(cx, bottomY) };
            using (SolidBrush ink = new SolidBrush(down ? Color.White : lit ? UiTheme.Accent : UiTheme.AccentStrong))
                g.FillPolygon(ink, triangle);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.Clear(BackColor);
            if (viewport.Range <= 0)
                return;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            // The rail: a hairline down the middle, as KOTOR's lists have.
            Rectangle rail = Rail;
            float mid = Width / 2F;
            using (Pen line = new Pen(UiTheme.Border))
                g.DrawLine(line, mid, rail.Top, mid, rail.Bottom);

            DrawArrowBox(g, UpBox, true, Part.Up);
            DrawArrowBox(g, DownBox, false, Part.Down);

            // The thumb: a framed bar with cut corners, and a grip of three short lines.
            Rectangle thumb = Thumb;
            bool dragging = pressed == Part.Thumb;
            bool lit = hover == Part.Thumb || dragging;
            RectangleF r = new RectangleF(thumb.X + 0.5F, thumb.Y + 0.5F, thumb.Width - 1F, thumb.Height - 1F);
            using (GraphicsPath frame = Chamfered(r, Math.Max(1.5F, thumb.Width / 4F)))
            using (SolidBrush fill = new SolidBrush(dragging ? UiTheme.AccentStrong : lit ? UiTheme.AccentDark
                                                                                    : Color.FromArgb(0, 58, 82)))
            using (Pen edge = new Pen(lit ? UiTheme.Accent : UiTheme.AccentStrong))
            {
                g.FillPath(fill, frame);
                g.DrawPath(edge, frame);
            }
            float spacing = Math.Max(2F, thumb.Width / 4F);
            if (thumb.Height > spacing * 5)
            {
                float cy = thumb.Y + thumb.Height / 2F;
                float half = thumb.Width * 0.22F;
                using (Pen grip = new Pen(dragging ? Color.White : UiTheme.Accent))
                    for (int i = -1; i <= 1; i++)
                        g.DrawLine(grip, mid - half, cy + i * spacing, mid + half, cy + i * spacing);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
                repeat.Dispose();
            base.Dispose(disposing);
        }
    }

    /// <summary>Cross-fades one view of the card into another.
    ///
    /// Both states are captured as bitmaps and this control paints the incoming one
    /// solid with the outgoing one over it at falling alpha. Painting two opaque bitmaps
    /// avoids WinForms' transparent-control behaviour entirely -- a genuinely translucent
    /// control samples its parent's background, which is exactly the thing being
    /// animated, and flickers.</summary>
    internal sealed class FadeOverlay : Control
    {
        private readonly Bitmap outgoing;
        private readonly Bitmap incoming;
        private float progress;

        internal FadeOverlay(Bitmap outgoingView, Bitmap incomingView)
        {
            outgoing = outgoingView;
            incoming = incomingView;
            SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                     ControlStyles.UserPaint, true);
            TabStop = false;
        }

        internal float Progress
        {
            get { return progress; }
            set
            {
                progress = value < 0F ? 0F : (value > 1F ? 1F : value);
                Invalidate();
            }
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            Rectangle box = new Rectangle(0, 0, Width, Height);
            if (incoming != null)
                g.DrawImage(incoming, box, 0, 0, incoming.Width, incoming.Height, GraphicsUnit.Pixel);
            if (outgoing == null || progress >= 1F)
                return;
            using (ImageAttributes attributes = new ImageAttributes())
            {
                ColorMatrix matrix = new ColorMatrix();
                matrix.Matrix33 = 1F - progress;
                attributes.SetColorMatrix(matrix);
                g.DrawImage(outgoing, box, 0, 0, outgoing.Width, outgoing.Height,
                            GraphicsUnit.Pixel, attributes);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (outgoing != null) outgoing.Dispose();
                if (incoming != null) incoming.Dispose();
            }
            base.Dispose(disposing);
        }
    }

    internal sealed class MainForm : Form
    {
        private delegate void UiOperation(Action<string> report, Action<int, string> progress);

        private sealed class FontTemplate
        {
            internal readonly string Family;
            internal readonly float Size;
            internal readonly FontStyle Style;
            internal readonly GraphicsUnit Unit;

            internal FontTemplate(Font font)
            {
                Family = font.FontFamily.Name;
                Size = font.Size;
                Style = font.Style;
                Unit = font.Unit;
            }

            internal Font Create(float scale)
            {
                return new Font(Family, Math.Max(6F, Size * scale), Style, Unit);
            }
        }

        internal const string AppName = "KOTOR Modern Restoration Patch";
        internal const string ShortName = "KMRP";
        // Derived, not restated: this said "v1.0.0" while PatchVersion and the
        // file's own version said 1.5.0, a second copy nobody updated.
        internal const string Version = "v" + GoldPatch.PatchVersion;
        // The header is measured from the brand artwork rather than fixed, so widening
        // the window scales the lockup and the card follows it down.
        // The lockup is sized against the card, not the window, so the two read as one
        // block: half the card's width, centred on it.
        private const double BrandCardFraction = 0.5;
        // The card is a fixed rectangle rather than something that stretches to the
        // window's edges: on a wide window a full-width row leaves a desert between a
        // step's subtitle and its control. Its height is fully determined by the row
        // heights below -- four steps, the gap above the action button, the button, and
        // the bottom padding -- so the width follows from the ratio.
        private const double CardAspect = 2.25;   // 1.5 was the first pass; this is 50% wider
        private const int StepHeight = 108;
        // Where the wordmark's ink actually ends inside the brand image, as a fraction of
        // its width. The PNG carries transparent margin and glow beyond the last letter, so
        // the drawn width is not the visible width -- measured on the artwork: the R's right
        // edge sits at 0.9774.
        private const double WordmarkInkRight = 0.9774;
        private const double WordmarkInkLeft = 0.0216;
        private const string Tagline = "M O D E R N .   R E S T O R E D .   S I M P L E .";
        private readonly int headerHeight;
        private readonly int brandWidth;
        private readonly int brandHeight;
        private const string CreatorUrl = "https://deadlystream.com/profile/68365-raymangt/";

        private readonly TextBox pathBox;              // data holder; the path is shown in step 1's subtitle
        private readonly PillButton actionButton;
        private bool actionIsRestore;
        // Beside Restore Original when this installer is a newer build than the KMRP
        // installed (LayoutActionRow).
        private readonly PillButton upgradeButton;
        private bool upgradeOffered;
        private Rectangle actionRowDesign;
        // Under the button, at its right, while an install makes KMRP's art: the time left
        // (ArtPreparation, KpmEdition.cs). Empty and hidden otherwise.
        private readonly Label timeLeftLabel;
        private readonly PillButton browseButton;
        private readonly StepRow stepFolder;
        private readonly StepRow stepVerify;
        private readonly StepRow stepResolution;
        private readonly StepRow stepApply;
        private readonly StateLabel verifyState;
        private readonly StateLabel resolutionState;
        private readonly StateLabel applyState;
        private readonly CardPanel mainCard;
        private readonly PillButton settingsButton;
        private readonly CardPanel settingsView;
        // Advanced Settings' tiles scroll since 2026-10-19 (a seventh came, Marked Empty
        // Containers): their viewport, its scrollbar, and the filter that sends the
        // mouse wheel to them.
        private readonly ScrollViewport settingsScroll;
        private readonly KotorScrollBar settingsScrollBar;
        private readonly SettingsWheel settingsWheel;
        private readonly OptionToggle driverToggle;
        private readonly OptionToggle markerToggle;
        private readonly OptionToggle controllerToggle;
        private readonly List<Control> mainViewControls = new List<Control>();
        private Timer fadeTimer;
        private FadeOverlay fadeOverlay;
        private bool settingsOpen;
        private readonly Panel optionsHost;           // reserved: future checkboxes land here
        private readonly LinkLabel logLink;
        private Image brand;
        private readonly LightField light = new LightField();
        // The header repaints on every animation frame, so the brand must not be
        // resampled on every one of them: a 650x350 bicubic resize per frame cost more
        // than the plume itself. Scaled once per size, then blitted.
        private Bitmap scaledBrand;
        // The plume is generated on its own thread into an off-screen surface; the UI
        // thread only blits the finished frame. Painting it inline cost the UI thread
        // about 20 ms of every 62 ms frame -- fine on an idle window, but not enough
        // headroom left to also service a dropdown being scrolled, which is what made the
        // animation stutter there.
        private System.Threading.Thread renderThread;
        private volatile bool renderRunning;
        private volatile int desiredHeaderW, desiredHeaderH;
        private Bitmap headerFront, headerBack;
        private readonly object headerSwap = new object();
        // The brand and tagline on transparency, composited into each frame by the render
        // thread. The render thread cannot draw them itself -- fonts and the scaled artwork
        // belong to the UI thread -- so they are baked here whenever the size changes.
        private Bitmap headerOverlay;
        private readonly object overlayLock = new object();
        // Presentation goes straight to the window from the render thread. Posting through
        // BeginInvoke put every frame in the message queue behind whatever else was there;
        // measured while scrolling the resolution dropdown, frames were produced with 1.0 ms
        // of jitter but waited up to 61.8 ms to reach the screen, which is a whole frame.
        private volatile IntPtr presentHwnd;
        private volatile bool allowDirectPresent;

        // 60ms, which Windows' 15.6ms timer granularity rounds to 62.4ms -- 16 fps,
        // against 46.8ms and 21.4 fps at the previous 40ms. A quarter fewer frames for a
        // quarter less CPU. See the mote fall speed, which was slowed to match: the two
        // must move together or the fastest motes start stepping.
        private const int AnimationIntervalMs = 60;
        private Font taglineFont;      // sized so the tagline matches the wordmark's width
        private bool operationRunning;
        private string lastDetail = String.Empty;
        // The most characters a step's line shows beside the state on its right.
        private const int StepLineLimit = 80;
        private readonly Dictionary<Control, Rectangle> designBounds = new Dictionary<Control, Rectangle>();
        private readonly Dictionary<Control, FontTemplate> designFonts = new Dictionary<Control, FontTemplate>();
        private readonly Dictionary<Control, Font> scaledFonts = new Dictionary<Control, Font>();
        private readonly List<Font> retiredFonts = new List<Font>();
        private readonly Timer fontRetireTimer;
        private Size designClientSize;
        private Size lastClientSize;
        private float uiScale = 1F;
        private float nativeFontScale = 1F;
        private Bitmap resizePreview;
        private bool resizePreviewActive;
        private int resizeHeaderHeight;
        private readonly List<Control> resizePreviewControls = new List<Control>();
        private bool resizeReady;
        private bool enforcingAspect;
        private bool initialFitApplied;
        private const float MinimumUiScale = 0.35F;
        private const int ReferenceWorkingWidth = 1920;
        private const int ReferenceWorkingHeight = 1040;
        private const int ReferenceWindowWidth = 1300;
        private const int ReferenceWindowHeight = 700;

        internal MainForm()
        {
            Text = ShortName + " – " + AppName;
            MaximizeBox = false;
            FormBorderStyle = FormBorderStyle.Sizable;
            SizeGripStyle = SizeGripStyle.Show;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.Dpi;
            DoubleBuffered = true;
            SetStyle(ControlStyles.OptimizedDoubleBuffer | ControlStyles.AllPaintingInWmPaint |
                ControlStyles.ResizeRedraw, true);
            Font = new Font("Segoe UI", 11F);
            BackColor = UiTheme.Window;
            ForeColor = UiTheme.Text;
            // WinForms can queue a LinkLabel paint while a resize is replacing its font.
            // Keep old scaled fonts alive until the resize/paint burst has gone idle.
            // ~25fps is plenty for a slow haze, and the field only ever invalidates the
            // header strip, so a frame costs one small bitmap and one upscale.


            fontRetireTimer = new Timer();
            fontRetireTimer.Interval = 750;
            fontRetireTimer.Tick += delegate
            {
                fontRetireTimer.Stop();
                DisposeRetiredFonts();
            };
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); }
            catch { }
            HandleCreated += delegate { UseDarkTitleBar(Handle); };
            try
            {
                using (Stream stream = Assembly.GetExecutingAssembly()
                           .GetManifestResourceStream("Kmrp.brand"))
                    if (stream != null)
                        brand = Image.FromStream(stream);
            }
            catch { brand = null; }

            // Height is the sum of the fixed pieces: four steps, the gap above the primary
            // action, the action button, and the bottom padding.
            int cardHeight = 4 * StepHeight + 30 + 76 + 40;
            int cardWidth = (int)Math.Round(cardHeight * CardAspect);

            brandWidth = (int)Math.Round(cardWidth * BrandCardFraction);
            brandHeight = brand == null ? 150
                : (int)Math.Round(brand.Height * (brandWidth / (double)brand.Width));
            headerHeight = 14 + brandHeight + 56;

            // The window's side margin is not a free choice: it is set equal to the gap
            // between the end of the wordmark and the card's edge, so the lockup, the card
            // and the window frame all breathe at the same rhythm. Both the card and the
            // lockup are centred, so that gap is cardWidth/2 minus how far the ink reaches
            // past the lockup's own centre.
            int gapInsideCard = (int)Math.Round(cardWidth / 2.0
                                                - (WordmarkInkRight - 0.5) * brandWidth);
            int clientWidth = cardWidth + 2 * gapInsideCard;
            ClientSize = new Size(clientWidth, 900);

            pathBox = new TextBox();
            pathBox.TextChanged += delegate { RefreshStatus(); };

            CardPanel card = new CardPanel();
            mainCard = card;
            card.SetBounds((ClientSize.Width - cardWidth) / 2, headerHeight, cardWidth, cardHeight);
            card.Anchor = AnchorStyles.Top;
            Controls.Add(card);

            stepFolder = NewStep(card, 0, UiTheme.Glyph.Folder, "1. Select Game Folder",
                "Choose your Knights of the Old Republic folder.");
            browseButton = new PillButton();
            browseButton.Text = "Browse";
            browseButton.TextSize = 18F;
            browseButton.SetBounds(card.Width - 168, 24, 132, 48);
            browseButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            browseButton.Click += delegate { BrowseForExecutable(this); };
            stepFolder.Controls.Add(browseButton);

            // Step 2 names the game version it finds; there is nothing to fetch. Until
            // 2026-09-30 it was "Verify Editable EXE", and it grew to offer "Get Editable
            // EXE" and "Check Again" when the file was not the editable one: KMRP now
            // takes Steam's, GOG's and the editable swkotor.exe as they are
            // (GameExecutable). The window checks again whenever it is activated, so a
            // file replaced meanwhile is seen on return.
            stepVerify = NewStep(card, 1, UiTheme.Glyph.Shield, "2. Detect Game Version",
                "Looking for swkotor.exe.");
            verifyState = NewStateLabel(stepVerify, card.Width);

            // Step 3 chooses nothing: KMRP's patch carries every resolution, the game
            // lists the sizes the connected display supports, and it starts at the
            // display's current size (ResolutionSelection). Until 2026-10-04 this was a
            // list to pick the one resolution KMRP was installed for, and until
            // 2026-10-07 it had a "Choose" button for a checklist of sizes.
            stepResolution = NewStep(card, 2, UiTheme.Glyph.Monitor, "3. Resolutions",
                ResolutionSelection.Summary());
            resolutionState = NewStateLabel(stepResolution, card.Width);
            resolutionState.Visible = false;

            stepApply = NewStep(card, 3, UiTheme.Glyph.Tools, "4. Apply Patch",
                "Patches will be applied to make KOTOR modern-ready.");
            stepApply.DrawSeparator = false;
            applyState = NewStateLabel(stepApply, card.Width);

            // Reserved for optional toggles (16:9 HUD safe zone on 21:9/32:9, and so on).
            // Empty and zero-height today; giving it a home now means adding one later is
            // a matter of dropping a checkbox in and growing the card, not a redesign.
            optionsHost = new Panel();
            optionsHost.SetBounds(0, 4 * 96, card.Width, 0);
            optionsHost.BackColor = UiTheme.Card;
            optionsHost.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            card.Controls.Add(optionsHost);

            // One action, whose identity follows the executable's state: patch a clean
            // install, restore a patched one. Two permanently visible buttons meant one of
            // them was always disabled, which reads as something being broken rather than
            // as a step that does not apply yet.
            actionButton = new PillButton();
            actionButton.Primary = true;
            actionButton.Text = "Start Patching";
            // The action row is one unit: the primary, a small gap, then a square
            // settings button of the same height. The square is sized from that height so
            // the two always agree, whatever the row height becomes.
            const int ActionHeight = 76;
            const int ActionGap = 12;
            // The card is a fixed height and the action row sits a fixed distance from
            // its bottom, so nothing below the card -- the footer, the window, the
            // settings view that covers it -- ever has to resize (StepRow.ActionRoom).
            actionButton.SetBounds(80, optionsHost.Bottom + 30 + StepRow.ActionRoom,
                                   card.Width - 160 - ActionGap - ActionHeight, ActionHeight);
            actionButton.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            actionButton.Click += ActionClicked;
            card.Controls.Add(actionButton);

            // Secondary, and square: same height and radius as the primary so it reads as
            // part of the same row, but card-filled with a muted border rather than the
            // lit gradient, so it never competes with Start Patching.
            settingsButton = new PillButton();
            settingsButton.Subtle = true;
            settingsButton.IconName = "Settings";
            settingsButton.SetBounds(actionButton.Right + ActionGap, actionButton.Top,
                                     ActionHeight, ActionHeight);
            settingsButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            settingsButton.Click += delegate { ShowSettings(true); };
            card.Controls.Add(settingsButton);

            ToolTip settingsTip = new ToolTip();
            settingsTip.SetToolTip(settingsButton, "Advanced Settings");

            // When an older KMRP is installed, the primary's place holds two buttons of
            // one size, Restore Original and Upgrade, and the settings button keeps its
            // own (the maintainer, 2026-10-19). Hidden otherwise; LayoutActionRow.
            upgradeButton = new PillButton();
            upgradeButton.Primary = true;
            upgradeButton.Text = "Upgrade";
            upgradeButton.SetBounds(actionButton.Left, actionButton.Top, actionButton.Width, ActionHeight);
            upgradeButton.Visible = false;
            upgradeButton.Click += UpgradeClicked;
            card.Controls.Add(upgradeButton);

            // The time left, out of the button, under its right end (the maintainer,
            // 2026-10-19: "make the seconds be outside of the button in the bottom right part
            // below the button"); the button keeps what is being done and the percentage.
            timeLeftLabel = new Label();
            timeLeftLabel.Font = new Font("Segoe UI", 13F);
            timeLeftLabel.ForeColor = UiTheme.TextMuted;
            timeLeftLabel.BackColor = UiTheme.Card;
            timeLeftLabel.TextAlign = ContentAlignment.MiddleRight;
            timeLeftLabel.SetBounds(actionButton.Left, actionButton.Bottom + 4, actionButton.Width, 32);
            timeLeftLabel.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            timeLeftLabel.Visible = false;
            card.Controls.Add(timeLeftLabel);

            card.Height = actionButton.Bottom + 40;

            // --- Settings -------------------------------------------------------
            // The settings view occupies the card, hidden until asked for. It is a
            // sibling of the step rows rather than a separate window so the cross-fade
            // has something to fade between and the window never changes size.
            // A CardPanel, not a plain Panel: it covers the card completely, so a
            // square one squared off the card's rounded corners for as long as settings
            // was open. This paints the same radius, fill and edge.
            settingsView = new CardPanel();
            settingsView.SetBounds(0, 0, card.Width, card.Height);
            settingsView.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            settingsView.Visible = false;
            card.Controls.Add(settingsView);

            Label settingsTitle = new Label();
            settingsTitle.Text = "Advanced Settings";
            settingsTitle.Font = new Font("Segoe UI Semibold", 24F);
            settingsTitle.ForeColor = UiTheme.Text;
            settingsTitle.BackColor = UiTheme.Card;
            settingsTitle.TextAlign = ContentAlignment.MiddleLeft;
            // The title and its line share one row since 2026-10-08, when a fifth
            // option needed the height the line had below the title.
            settingsTitle.SetBounds(36, 16, 340, 44);
            settingsTitle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            settingsView.Controls.Add(settingsTitle);

            Label settingsSubtitle = new Label();
            settingsSubtitle.Text =
                "Each can be changed on its own. Restore Defaults puts them back.";
            settingsSubtitle.Font = new Font("Segoe UI", 14F);
            settingsSubtitle.ForeColor = UiTheme.TextMuted;
            settingsSubtitle.BackColor = UiTheme.Card;
            settingsSubtitle.TextAlign = ContentAlignment.MiddleRight;
            settingsSubtitle.SetBounds(settingsTitle.Right, settingsTitle.Top + 4,
                                       card.Width - 36 - settingsTitle.Right, settingsTitle.Height - 4);
            settingsSubtitle.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            settingsView.Controls.Add(settingsSubtitle);

            // Tiles three to a row, in the order the maintainer set on 2026-10-09, read row
            // by row: controller support first, then the bundled work of others, debug
            // logs last. Six, three by two, filled what the card has between the title and
            // the buttons from that day (rows until then: four, then five on 2026-10-08,
            // then six that morning). Since 2026-10-19 there are seven, Marked Empty
            // Containers after High FPS Fix: the tiles keep the size six had, two rows in
            // view, and the rows scroll, with a scrollbar after KOTOR's in the card's
            // right margin (the maintainer's choice over a narrower or shorter grid).
            int optionGap = 10;
            int optionWidth = (card.Width - 72 - 2 * optionGap) / 3;
            int optionRowTop = settingsTitle.Bottom + 10;
            int optionViewHeight = card.Height - 96 - 8 - optionRowTop;
            int optionRowHeight = (optionViewHeight - optionGap) / 2;
            const int optionRows = 3;
            // Tile positions inside the scrolled panel.
            int optionFirstTop = 0;
            int optionSecondTop = optionRowHeight + optionGap;
            int optionThirdTop = 2 * (optionRowHeight + optionGap);
            int optionColumn1 = 0;
            int optionColumn2 = optionWidth + optionGap;
            int optionColumn3 = optionColumn2 + optionWidth + optionGap;

            settingsScroll = new ScrollViewport();
            settingsScroll.SetBounds(36, optionRowTop, card.Width - 72, optionViewHeight);
            settingsScroll.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            settingsScroll.DesignStep = optionRowHeight + optionGap;
            settingsScroll.Content.SetBounds(0, 0, card.Width - 72,
                optionRows * optionRowHeight + (optionRows - 1) * optionGap);
            settingsView.Controls.Add(settingsScroll);
            ScrollContent optionPanel = settingsScroll.Content;

            // In the middle of the 36-pixel margin, as far from the tiles as from the
            // card's edge.
            const int scrollBarWidth = 14;
            settingsScrollBar = new KotorScrollBar(settingsScroll);
            settingsScrollBar.SetBounds(card.Width - 36 + (36 - scrollBarWidth) / 2, optionRowTop,
                                        scrollBarWidth, optionViewHeight);
            settingsScrollBar.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            settingsView.Controls.Add(settingsScrollBar);
            settingsWheel = new SettingsWheel(this);
            Application.AddMessageFilter(settingsWheel);

            controllerToggle = new OptionToggle();
            // What ships now, in one line: KMRP's native controller path with SDL3 beside
            // XInput, reading the pad family for its prompts. Saul0097's KPM Xbox Controls
            // is where it began and is still credited in THIRD_PARTY_NOTICES.md and the
            // README. The author line here named him too ("KMRP, based on Saul0097")
            // until 2026-10-05, when the maintainer asked for the public-facing credit to
            // be KMRP's alone, and reads "RaymanGT" since 2026-10-09 ("KMRP" until then),
            // with the row named "Native Controller Support" ("Controller Support"
            // before); the notices and the documentation are unchanged.
            controllerToggle.Title = "Native Controller Support";
            controllerToggle.Author = "RaymanGT";
            controllerToggle.Detail =
                "Xbox, PlayStation, Switch and Steam Deck pads: prompts, rumble and the Xbox-style HUD.";
            controllerToggle.Checked = KmrpSettings.ControllerSupport;
            controllerToggle.SetBounds(optionColumn1, optionFirstTop, optionWidth, optionRowHeight);
            controllerToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            controllerToggle.CheckedChanged += delegate
            {
                KmrpSettings.ControllerSupport = controllerToggle.Checked;
            };
            optionPanel.Controls.Add(controllerToggle);

            driverToggle = new OptionToggle();
            driverToggle.Title = "Modern Driver Compatibility";
            driverToggle.Author = "Synchro";
            driverToggle.Detail =
                "Fixes lighting, fog, reflections, soft shadows and grass on modern graphics cards.";
            driverToggle.Checked = KmrpSettings.DriverCompatibility && DriverCompatOperations.CanRunHere;
            driverToggle.SetBounds(optionColumn2, optionFirstTop, optionWidth, optionRowHeight);
            driverToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            // Off and disabled where K1DC cannot run (Windows 7): installed there, it
            // would keep the game from starting. Set before the handler below, so the
            // player's saved choice is kept for a PC that can run it.
            if (!DriverCompatOperations.CanRunHere)
            {
                driverToggle.Enabled = false;
                driverToggle.Note = "Needs Windows 8";
                driverToggle.NoteColor = UiTheme.Warning;
            }
            // Independent of the controller since 2026-09-24. This option installs
            // K1DC's ASI loader and its .asi together (DriverCompatOperations.Install);
            // KMRP's runtime needs neither since 2026-09-29, when it moved to KOTOR
            // Patch Manager's binkw32.dll proxy.
            driverToggle.CheckedChanged += delegate
            {
                KmrpSettings.DriverCompatibility = driverToggle.Checked;
            };
            optionPanel.Controls.Add(driverToggle);

            markerToggle = new OptionToggle();
            markerToggle.Title = "Area Map Marker Fixes";
            markerToggle.Author = "Derslok";
            markerToggle.Detail =
                "Corrects misplaced area-map marker positions across the game.";
            markerToggle.Checked = KmrpSettings.MarkerFixes;
            markerToggle.SetBounds(optionColumn3, optionFirstTop, optionWidth, optionRowHeight);
            markerToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            markerToggle.CheckedChanged += delegate
            {
                KmrpSettings.MarkerFixes = markerToggle.Checked;
            };
            optionPanel.Controls.Add(markerToggle);

            // The patch's hd-icons option, a row since 2026-10-08.
            OptionToggle iconsToggle = new OptionToggle();
            iconsToggle.Title = "HD Item Icons";
            iconsToggle.Author = "JackInTheBox";
            iconsToggle.Detail =
                "High-resolution item icons. Turn off to keep the game's own icons.";
            iconsToggle.Checked = KmrpSettings.HdIcons;
            iconsToggle.SetBounds(optionColumn1, optionSecondTop, optionWidth, optionRowHeight);
            iconsToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            iconsToggle.CheckedChanged += delegate
            {
                KmrpSettings.HdIcons = iconsToggle.Checked;
            };
            optionPanel.Controls.Add(iconsToggle);

            // D3M0's High FPS Fixes, a third patch, off unless turned on here: a row
            // since 2026-10-09.
            OptionToggle fpsToggle = new OptionToggle();
            fpsToggle.Title = "High FPS Fix";
            fpsToggle.Author = "D3M0";
            fpsToggle.Detail =
                "Fixes timing and animation faults above 60 frames per second." +
                (KmrpSettings.HighFpsFixAuto ? " On by default for this display."
                                             : " Off by default on a 60 Hz display.");
            // In green beside the title, at the maintainer's request (2026-10-09): the
            // highest rate the display reports, where that is above 60.
            if (KmrpSettings.HighFpsFixAuto)
                fpsToggle.Note = "Display supports " +
                    KmrpSettings.DisplayRefresh.ToString(CultureInfo.InvariantCulture) + " Hz";
            fpsToggle.Checked = KmrpSettings.HighFpsFix;
            fpsToggle.SetBounds(optionColumn2, optionSecondTop, optionWidth, optionRowHeight);
            fpsToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            fpsToggle.CheckedChanged += delegate
            {
                KmrpSettings.HighFpsFix = fpsToggle.Checked;
            };
            optionPanel.Controls.Add(fpsToggle);

            // ShaeMyName's Marked Empty Containers, a fourth patch, on by default: a tile
            // since 2026-10-19 (issue 43).
            OptionToggle emptyToggle = new OptionToggle();
            emptyToggle.Title = "Marked Empty Containers";
            emptyToggle.Author = "ShaeMyName";
            emptyToggle.Detail =
                "Adds \"(empty)\" to the name of a container or body with nothing left in it.";
            emptyToggle.Checked = KmrpSettings.MarkedEmptyContainers;
            emptyToggle.SetBounds(optionColumn3, optionSecondTop, optionWidth, optionRowHeight);
            emptyToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            emptyToggle.CheckedChanged += delegate
            {
                KmrpSettings.MarkedEmptyContainers = emptyToggle.Checked;
            };
            optionPanel.Controls.Add(emptyToggle);

            // The patch's debug-logs option: off by default, for a player who was asked
            // for logs with a bug report.
            OptionToggle debugToggle = new OptionToggle();
            debugToggle.Title = "Debug Logs";
            debugToggle.Author = "KMRP";
            debugToggle.Detail =
                "Writes diagnostic log files beside the game. Turn on when reporting a problem.";
            debugToggle.Checked = KmrpSettings.DebugLogs;
            debugToggle.SetBounds(optionColumn1, optionThirdTop, optionWidth, optionRowHeight);
            debugToggle.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            debugToggle.CheckedChanged += delegate
            {
                KmrpSettings.DebugLogs = debugToggle.Checked;
            };
            optionPanel.Controls.Add(debugToggle);

            // An earlier fourth row, "KOTOR Patch Manager", installed for KPM on request from
            // 2026-09-29 to 2026-09-30. It was removed: KPM's files in the game folder
            // choose that install by themselves, and KMRP's own install is one KPM
            // recognises and can take over (kpm_install_state.json, its backup, the
            // .kpatch files in its folder), so it only decided who installed the runtime
            // first -- and on Steam with KPM 0.7.1 it left a runtime KPM injected, which a
            // game Steam starts never loads. (A Movie Fixes row was a fourth for a few
            // hours on 2026-10-04; the maintainer made the movie fixes part of KMRP, not
            // an option. Debug Logs is the fourth since later that day.)

            // Two actions, sharing the row the single Back button used to have. Restore
            // Defaults is Subtle so Back stays the obvious way out.
            int settingsRowTop = card.Height - 96;
            int settingsRowWidth = (card.Width - 160 - 12) / 2;

            PillButton settingsDefaults = new PillButton();
            settingsDefaults.Subtle = true;
            settingsDefaults.Text = "Restore Defaults";
            settingsDefaults.SetBounds(80, settingsRowTop, settingsRowWidth, 60);
            settingsDefaults.Anchor = AnchorStyles.Top | AnchorStyles.Left;
            settingsDefaults.Click += delegate
            {
                // The documented defaults: the three components on, debug logs off
                // (KmrpSettings).
                driverToggle.Checked = DriverCompatOperations.CanRunHere;
                markerToggle.Checked = true;
                iconsToggle.Checked = true;
                emptyToggle.Checked = true;
                controllerToggle.Checked = true;
                // High FPS Fix follows the display again: the toggle first, since
                // setting it records a choice, then the choice forgotten.
                fpsToggle.Checked = KmrpSettings.HighFpsFixAuto;
                KmrpSettings.ResetHighFpsFix();
                debugToggle.Checked = false;
            };
            settingsView.Controls.Add(settingsDefaults);

            PillButton settingsBack = new PillButton();
            settingsBack.Text = "Back";
            settingsBack.SetBounds(settingsDefaults.Right + 12, settingsRowTop,
                                   settingsRowWidth, 60);
            settingsBack.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            settingsBack.Click += delegate { ShowSettings(false); };
            settingsView.Controls.Add(settingsBack);

            // Everything the settings view replaces. Captured after the card is fully
            // populated so nothing is missed, and excluding the settings view itself.
            foreach (Control child in card.Controls)
                if (child != settingsView)
                    mainViewControls.Add(child);

            logLink = new LinkLabel();
            logLink.Text = Version + "   ·   Open Log";
            logLink.LinkArea = new LinkArea(Version.Length + 7, 8);
            logLink.Font = new Font("Segoe UI Semibold", 15.5F);
            logLink.ForeColor = UiTheme.TextFaint;
            logLink.LinkColor = UiTheme.Accent;
            logLink.ActiveLinkColor = Color.White;
            logLink.VisitedLinkColor = UiTheme.Accent;
            logLink.LinkBehavior = LinkBehavior.HoverUnderline;
            logLink.BackColor = UiTheme.Window;
            logLink.TextAlign = ContentAlignment.MiddleLeft;
            logLink.SetBounds(card.Left + 8, card.Bottom + 14, 240, 34);
            logLink.Anchor = AnchorStyles.Top;
            logLink.LinkClicked += OpenLogClicked;
            Controls.Add(logLink);

            LinkLabel credit = new LinkLabel();
            credit.Text = "Created by RaymanGT";
            credit.Font = new Font("Segoe UI Semibold", 15.5F);
            credit.LinkColor = UiTheme.TextFaint;
            credit.ActiveLinkColor = UiTheme.Accent;
            credit.VisitedLinkColor = UiTheme.TextFaint;
            credit.LinkBehavior = LinkBehavior.HoverUnderline;
            credit.BackColor = UiTheme.Window;
            credit.TextAlign = ContentAlignment.MiddleRight;
            // 260 wide, not 220. "Created by RaymanGT" measures 218px in Segoe UI but
            // 228px in Semibold, so the old box clipped it: a LinkLabel wraps rather than
            // ellipsises, and at 34 tall only the first line showed. The headroom also
            // covers the hinting differences that stop glyph widths scaling perfectly
            // linearly with point size. The right edge is unchanged at card.Right - 8.
            credit.SetBounds(card.Right - 268, card.Bottom + 14, 260, 34);
            credit.Anchor = AnchorStyles.Top;
            credit.LinkClicked += delegate { OpenCreatorPage(); };
            Controls.Add(credit);

            ClientSize = new Size(ClientSize.Width, credit.Bottom + 18);

            // Every element keeps a design-space rectangle. Resizing reapplies those
            // rectangles at one uniform scale, so type, spacing, icons, hit targets and
            // artwork all grow together instead of stretching independently.
            designClientSize = ClientSize;
            lastClientSize = ClientSize;
            CaptureDesignLayout(this);
            MinimumSize = SizeFromClientSize(new Size(
                (int)Math.Round(designClientSize.Width * MinimumUiScale),
                (int)Math.Round(designClientSize.Height * MinimumUiScale)));
            MaximumSize = Size.Empty;

            pathBox.Text = FindDefaultExecutable();
            RefreshStatus();
            resizeReady = true;

            Activated += delegate { RefreshStatus(); };
            FormClosing += delegate(object sender, FormClosingEventArgs e)
            {
                if (!operationRunning)
                    return;
                e.Cancel = true;
                MessageBox.Show(this, "Please wait for the current operation to finish.", "Patcher is working",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            };
        }

        /// <summary>Everything that has to be settled before the window is displayed.
        /// The fit used to run on Shown, which meant the window appeared at its full
        /// design size and then snapped to the fitted size in front of the user.</summary>
        protected override void OnLoad(EventArgs e)
        {
            base.OnLoad(e);
            FitInitialSizeToWorkingArea();

            presentHwnd = Handle;
            desiredHeaderW = Math.Max(1, ClientSize.Width);
            desiredHeaderH = Math.Max(1, ScaleDesign(headerHeight));
            EnsureHeaderOverlay(desiredHeaderW, desiredHeaderH);
            // One frame composed up front, so the very first paint already carries the
            // plume instead of showing a flat header that pops a frame later.
            ComposeFrame(desiredHeaderW, desiredHeaderH);
            UpdatePresentMode();
        }

        /// <summary>Started only once the window has been shown and painted. Presenting
        /// straight to the window before WinForms has drawn the client area leaves the
        /// header sitting over unpainted desktop.</summary>
        protected override void OnShown(EventArgs e)
        {
            base.OnShown(e);
            if (!updateCheckStarted)
            {
                updateCheckStarted = true;
                StartUpdateCheck();
            }
            if (renderThread != null)
                return;
            renderRunning = true;
            renderThread = new System.Threading.Thread(RenderLoop);
            renderThread.IsBackground = true;
            // Below normal: the plume must never win a scheduling contest against the UI
            // thread, or against the file work during a patch.
            renderThread.Priority = System.Threading.ThreadPriority.BelowNormal;
            renderThread.Start();
        }

        protected override void OnResize(EventArgs e)
        {
            base.OnResize(e);
            if (!resizeReady || enforcingAspect || WindowState != FormWindowState.Normal ||
                ClientSize.Width <= 0 || ClientSize.Height <= 0)
                return;

            Size requested = ClientSize;
            double widthDelta = Math.Abs(requested.Width - lastClientSize.Width) /
                (double)Math.Max(1, designClientSize.Width);
            double heightDelta = Math.Abs(requested.Height - lastClientSize.Height) /
                (double)Math.Max(1, designClientSize.Height);
            float requestedScale = widthDelta >= heightDelta
                ? requested.Width / (float)designClientSize.Width
                : requested.Height / (float)designClientSize.Height;
            float scale = Math.Max(MinimumUiScale, requestedScale);
            Size proportional = new Size(
                Math.Max(1, (int)Math.Round(designClientSize.Width * scale)),
                Math.Max(1, (int)Math.Round(designClientSize.Height * scale)));

            enforcingAspect = true;
            try
            {
                if (ClientSize != proportional)
                    ClientSize = proportional;
                if (resizePreviewActive)
                    Invalidate();
                else
                    ApplyUniformScale(scale);
                lastClientSize = ClientSize;
            }
            finally
            {
                enforcingAspect = false;
            }
        }

        protected override void OnResizeBegin(EventArgs e)
        {
            base.OnResizeBegin(e);
            BeginResizePreview();
        }

        protected override void OnResizeEnd(EventArgs e)
        {
            EndResizePreview();
            base.OnResizeEnd(e);
        }

        private void BeginResizePreview()
        {
            if (!resizeReady || resizePreviewActive || ClientSize.Width <= 0 || ClientSize.Height <= 0)
                return;

            // Finish any pending state/paint work before freezing the visual frame. This
            // prevents a partially painted recovery panel from becoming the resize preview.
            if (!operationRunning)
                RefreshStatus();
            Refresh();

            Bitmap preview = null;
            try
            {
                preview = new Bitmap(ClientSize.Width, ClientSize.Height,
                    System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
                using (Graphics capture = Graphics.FromImage(preview))
                {
                    Point clientOrigin = PointToScreen(Point.Empty);
                    capture.CopyFromScreen(clientOrigin, Point.Empty, ClientSize,
                        CopyPixelOperation.SourceCopy);
                }
            }
            catch
            {
                if (preview != null)
                    preview.Dispose();
                return;
            }

            resizePreview = preview;
            resizePreviewActive = true;

            resizeHeaderHeight = ScaleDesign(headerHeight);
            UpdatePresentMode();
            resizePreviewControls.Clear();
            foreach (Control child in Controls)
            {
                if (!child.Visible)
                    continue;
                resizePreviewControls.Add(child);
                child.Visible = false;
            }
            Invalidate();
        }

        private void EndResizePreview()
        {
            if (!resizePreviewActive)
                return;

            try
            {
                float finalScale = Math.Max(MinimumUiScale,
                    ClientSize.Width / (float)Math.Max(1, designClientSize.Width));
                ApplyUniformScale(finalScale);
            }
            finally
            {
                resizePreviewActive = false;
                UpdatePresentMode();
                foreach (Control child in resizePreviewControls)
                    child.Visible = true;
                resizePreviewControls.Clear();

                if (resizePreview != null)
                {
                    resizePreview.Dispose();
                    resizePreview = null;
                }


                if (!operationRunning)
                    RefreshStatus();
                Invalidate(true);
                foreach (Control child in Controls)
                    child.Invalidate(true);
                Update();
            }
        }

        private void FitInitialSizeToWorkingArea()
        {
            if (initialFitApplied)
                return;
            initialFitApplied = true;

            Rectangle workArea = Screen.FromHandle(Handle).WorkingArea;
            int nonClientWidth = Math.Max(0, Width - ClientSize.Width);
            int nonClientHeight = Math.Max(0, Height - ClientSize.Height);

            // The user's approved 1080p composition is a centred 1300x700 window.
            // Scale that physical footprint uniformly from the active monitor's usable
            // dimensions. On ultrawide displays the height becomes the limiting axis,
            // which keeps the patcher comfortably sized instead of stretching with width.
            float referenceUiScale = Math.Min(
                Math.Max(1F, ReferenceWindowWidth - nonClientWidth) /
                    Math.Max(1, designClientSize.Width),
                Math.Max(1F, ReferenceWindowHeight - nonClientHeight) /
                    Math.Max(1, designClientSize.Height));
            float monitorScale = Math.Min(
                workArea.Width / (float)ReferenceWorkingWidth,
                workArea.Height / (float)ReferenceWorkingHeight);
            float startupScale = referenceUiScale * monitorScale;

            // Always retain a small safety margin for the taskbar and unusual aspect ratios.
            float fitScale = Math.Min(
                Math.Max(1F, workArea.Width * 0.94F - nonClientWidth) /
                    Math.Max(1, designClientSize.Width),
                Math.Max(1F, workArea.Height * 0.94F - nonClientHeight) /
                    Math.Max(1, designClientSize.Height));
            startupScale = Math.Min(startupScale, fitScale);
            startupScale = Math.Max(MinimumUiScale, startupScale);

            ClientSize = new Size(
                Math.Max(1, (int)Math.Round(designClientSize.Width * startupScale)),
                Math.Max(1, (int)Math.Round(designClientSize.Height * startupScale)));
            Location = new Point(
                workArea.Left + Math.Max(0, (workArea.Width - Width) / 2),
                workArea.Top + Math.Max(0, (workArea.Height - Height) / 2));

            // The initial fit changes every control after the first shown frame. Repaint
            // the resolved state immediately so the recovery panel never waits for a click.
            if (!operationRunning)
                RefreshStatus();
            Refresh();
        }

        private void CaptureDesignLayout(Control parent)
        {
            foreach (Control child in parent.Controls)
            {
                designBounds[child] = child.Bounds;
                if (child is Label || child is LinkLabel || child is ComboBox || child is TextBox ||
                    child is StateLabel)
                    designFonts[child] = new FontTemplate(child.Font);
                CaptureDesignLayout(child);
            }
        }

        private void ApplyUniformScale(float scale)
        {
            uiScale = Math.Max(MinimumUiScale, scale);
            SuspendLayoutTree(this);
            try
            {
                bool updateNativeFonts = Math.Abs(uiScale - nativeFontScale) >= 0.01F;
                ApplyControlScale(this, uiScale, updateNativeFonts);
                if (updateNativeFonts)
                    nativeFontScale = uiScale;
                if (taglineFont != null)
                {
                    taglineFont.Dispose();
                    taglineFont = null;
                }
            }
            finally
            {
                ResumeLayoutTree(this);
                Invalidate(true);
            }
        }

        private void ApplyControlScale(Control parent, float scale, bool updateNativeFonts)
        {
            foreach (Control child in parent.Controls)
            {
                FontTemplate template;
                if (updateNativeFonts && designFonts.TryGetValue(child, out template))
                {
                    Font replacement = template.Create(scale);
                    Font previous;
                    child.Font = replacement;
                    if (scaledFonts.TryGetValue(child, out previous))
                        retiredFonts.Add(previous);
                    scaledFonts[child] = replacement;
                }

                Rectangle logical;
                if (designBounds.TryGetValue(child, out logical))
                {
                    child.SetBounds(
                        (int)Math.Round(logical.X * scale),
                        (int)Math.Round(logical.Y * scale),
                        Math.Max(1, (int)Math.Round(logical.Width * scale)),
                        Math.Max(1, (int)Math.Round(logical.Height * scale)));
                }

                CardPanel cardPanel = child as CardPanel;
                if (cardPanel != null)
                    cardPanel.UiScale = scale;
                StepRow stepRow = child as StepRow;
                if (stepRow != null)
                    stepRow.UiScale = scale;
                PillButton pillButton = child as PillButton;
                if (pillButton != null)
                    pillButton.UiScale = scale;
                DarkCombo darkCombo = child as DarkCombo;
                if (darkCombo != null)
                    darkCombo.SetUiScale(scale);
                StateLabel stateLabel = child as StateLabel;
                if (stateLabel != null)
                    stateLabel.UiScale = scale;
                OptionToggle optionToggle = child as OptionToggle;
                if (optionToggle != null)
                    optionToggle.UiScale = scale;
                ScrollViewport scrollViewport = child as ScrollViewport;
                if (scrollViewport != null)
                    scrollViewport.UiScale = scale;

                ApplyControlScale(child, scale, updateNativeFonts);
            }

            if (retiredFonts.Count > 0)
            {
                fontRetireTimer.Stop();
                fontRetireTimer.Start();
            }
        }

        private static void SuspendLayoutTree(Control parent)
        {
            parent.SuspendLayout();
            foreach (Control child in parent.Controls)
                SuspendLayoutTree(child);
        }

        private static void ResumeLayoutTree(Control parent)
        {
            foreach (Control child in parent.Controls)
                ResumeLayoutTree(child);
            parent.ResumeLayout(false);
        }

        private void DisposeRetiredFonts()
        {
            foreach (Font font in retiredFonts)
                font.Dispose();
            retiredFonts.Clear();
        }

        /// <summary>Generates frames on a private thread and hands each finished surface to
        /// the UI thread to blit. Everything expensive -- the noise, the upscale, the mote
        /// sprites -- happens here, so the UI thread cost of a frame is one opaque blit
        /// rather than the whole render.
        ///
        /// Timing comes from a Stopwatch, not Environment.TickCount. TickCount advances in
        /// ~15.6 ms steps, so at a 62 ms frame it quantises the delta by nearly a quarter
        /// and the plume pulses.</summary>
        private void RenderLoop()
        {
            Stopwatch clock = Stopwatch.StartNew();
            double last = 0;
            while (renderRunning)
            {
                double now = clock.Elapsed.TotalSeconds;
                float seconds = (float)Math.Min(0.25, Math.Max(0.0, now - last));
                last = now;

                int w = desiredHeaderW, h = desiredHeaderH;
                if (w > 0 && h > 0)
                {
                    try
                    {
                        light.Step(seconds);
                        ComposeFrame(w, h);

                        IntPtr hwnd = presentHwnd;
                        if (allowDirectPresent && hwnd != IntPtr.Zero)
                            PresentDirect(hwnd, w, h);
                        else if (IsHandleCreated && !IsDisposed)
                            BeginInvoke((MethodInvoker)PresentHeader);
                    }
                    catch
                    {
                        // The handle can disappear mid-frame while closing. The loop exits
                        // on renderRunning either way.
                    }
                }

                double spent = (clock.Elapsed.TotalSeconds - now) * 1000.0;
                int rest = (int)Math.Round(AnimationIntervalMs - spent);
                System.Threading.Thread.Sleep(rest > 1 ? rest : 1);
            }
        }

        /// <summary>Blits the finished frame straight to the window from the render
        /// thread, bypassing the message queue entirely. Legal from a non-UI thread: this
        /// takes its own device context for the window and draws one opaque bitmap into it.
        /// It is serialised against the UI thread through the same lock the surfaces are
        /// swapped under, so the two never draw at once. Disabled while a resize preview is
        /// up, where the UI thread owns the frame, and while minimised.</summary>
        private void PresentDirect(IntPtr hwnd, int w, int h)
        {
            try
            {
                lock (headerSwap)
                {
                    if (headerFront == null)
                        return;
                    using (Graphics g = Graphics.FromHwnd(hwnd))
                    {
                        g.CompositingMode = CompositingMode.SourceCopy;
                        g.DrawImageUnscaled(headerFront, 0, 0);
                    }
                }
            }
            catch
            {
                // The window can be destroyed underneath this; the next frame re-checks.
            }
        }

        /// <summary>Bakes the brand and tagline onto transparency at the current header
        /// size. Runs on the UI thread because it needs the scaled artwork and the fonts;
        /// the render thread only composites the result.</summary>
        private void EnsureHeaderOverlay(int w, int h)
        {
            if (w < 1 || h < 1)
                return;
            lock (overlayLock)
            {
                if (headerOverlay != null && headerOverlay.Width == w && headerOverlay.Height == h)
                    return;
            }
            Bitmap baked = null;
            try
            {
                baked = new Bitmap(w, h, PixelFormat.Format32bppArgb);
                using (Graphics g = Graphics.FromImage(baked))
                {
                    g.Clear(Color.Transparent);
                    g.SmoothingMode = SmoothingMode.AntiAlias;
                    // Not ClearType: subpixel hinting against transparency leaves coloured
                    // fringes once the layer is composited.
                    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                    PaintBrandLayer(g, w);
                }
            }
            catch
            {
                if (baked != null)
                {
                    baked.Dispose();
                    baked = null;
                }
            }
            if (baked == null)
                return;
            lock (overlayLock)
            {
                if (headerOverlay != null)
                    headerOverlay.Dispose();
                headerOverlay = baked;
            }
        }

        /// <summary>Direct presentation is off while the UI thread owns the frame -- during
        /// a resize preview -- and while minimised.</summary>
        private void UpdatePresentMode()
        {
            allowDirectPresent = !resizePreviewActive
                && WindowState != FormWindowState.Minimized
                && !IsDisposed;
        }

        /// <summary>Draws one finished header -- background, plume, then the baked brand
        /// overlay -- into the back surface and swaps it to the front. The frame leaves
        /// here complete, so presenting it is a single opaque blit with nothing left for
        /// the UI thread to draw on top.</summary>
        private void ComposeFrame(int w, int h)
        {
            if (headerBack == null || headerBack.Width != w || headerBack.Height != h)
            {
                if (headerBack != null)
                    headerBack.Dispose();
                headerBack = new Bitmap(w, h, PixelFormat.Format32bppPArgb);
            }
            using (Graphics g = Graphics.FromImage(headerBack))
            {
                g.Clear(UiTheme.Window);
                light.Render(g, new Rectangle(0, 0, w, h));
                lock (overlayLock)
                {
                    if (headerOverlay != null)
                    {
                        if (headerOverlay.Width == w && headerOverlay.Height == h)
                            g.DrawImageUnscaled(headerOverlay, 0, 0);
                        else
                        {
                            g.InterpolationMode = InterpolationMode.HighQualityBilinear;
                            g.DrawImage(headerOverlay, 0, 0, w, h);
                        }
                    }
                }
            }
            // The surfaces are swapped, never shared: the UI thread reads the front while
            // the render thread draws the back.
            lock (headerSwap)
            {
                Bitmap spare = headerFront;
                headerFront = headerBack;
                headerBack = spare;
            }
        }

        /// <summary>Runs on the UI thread when a frame is ready. Update() rather than
        /// waiting for WM_PAINT, which is the lowest priority message there is and would be
        /// starved by the same wheel-message flood this design exists to survive.</summary>
        private void PresentHeader()
        {
            if (IsDisposed || Disposing || WindowState == FormWindowState.Minimized)
                return;
            Invalidate(new Rectangle(0, 0, ClientSize.Width, LiveHeaderHeight()));
            Update();
        }

        /// <summary>Blits the most recent finished frame, and tells the render thread what
        /// size to produce next. SourceCopy because the surface is opaque -- it carries its
        /// own background -- which makes this a straight copy rather than an alpha blend.</summary>
        private void BlitHeader(Graphics g, Rectangle area)
        {
            desiredHeaderW = Math.Max(1, area.Width);
            desiredHeaderH = Math.Max(1, area.Height);
            lock (headerSwap)
            {
                if (headerFront == null)
                {
                    using (SolidBrush back = new SolidBrush(UiTheme.Window))
                        g.FillRectangle(back, area);
                    return;
                }
                CompositingMode previousMode = g.CompositingMode;
                InterpolationMode previousInterp = g.InterpolationMode;
                g.CompositingMode = CompositingMode.SourceCopy;
                if (headerFront.Width == area.Width && headerFront.Height == area.Height)
                {
                    g.DrawImageUnscaled(headerFront, area.X, area.Y);
                }
                else
                {
                    // Only transiently, while the render thread catches up with a resize.
                    g.InterpolationMode = InterpolationMode.Bilinear;
                    g.DrawImage(headerFront, area);
                }
                g.CompositingMode = previousMode;
                g.InterpolationMode = previousInterp;
            }
        }

        /// <summary>Height of the header as it is currently being painted. While a resize
        /// preview is up, uiScale still holds its pre-resize value and the snapshot is
        /// being stretched, so the header's on-screen height is the captured height scaled
        /// by how far the window has been dragged -- which can be taller than the capture.
        /// Invalidating the captured height instead would leave a stale band behind when
        /// the window grows.</summary>
        private int LiveHeaderHeight()
        {
            if (resizePreviewActive && resizePreview != null && resizePreview.Height > 0)
                return Math.Max(1, (int)Math.Round(
                    resizeHeaderHeight * (double)ClientSize.Height / resizePreview.Height));
            return ScaleDesign(headerHeight);
        }

        private int ScaleDesign(int value)
        {
            return Math.Max(1, (int)Math.Round(value * uiScale));
        }

        /// <summary>Windows sends the mouse wheel to the focused control, and on Advanced
        /// Settings that is none of the tiles (they take no focus), so the window looks at
        /// every wheel message first and scrolls the tiles while the pointer is over them
        /// or their scrollbar.</summary>
        private sealed class SettingsWheel : IMessageFilter
        {
            private const int WmMouseWheel = 0x020A;
            private readonly MainForm form;

            internal SettingsWheel(MainForm form)
            {
                this.form = form;
            }

            public bool PreFilterMessage(ref Message m)
            {
                if (m.Msg != WmMouseWheel)
                    return false;
                int delta = (short)((m.WParam.ToInt64() >> 16) & 0xFFFF);
                return form.WheelOverSettings(delta);
            }
        }

        private bool WheelOverSettings(int delta)
        {
            if (!settingsOpen || !settingsView.Visible || settingsScroll.Range <= 0)
                return false;
            Point pointer = Cursor.Position;
            Rectangle area = Rectangle.Union(settingsScroll.RectangleToScreen(settingsScroll.ClientRectangle),
                                             settingsScrollBar.RectangleToScreen(settingsScrollBar.ClientRectangle));
            if (!area.Contains(pointer))
                return false;
            settingsScroll.Wheel(delta);
            return true;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                Application.RemoveMessageFilter(settingsWheel);
                FinishFade();
                fontRetireTimer.Stop();
                fontRetireTimer.Dispose();
                DisposeRetiredFonts();
                foreach (Font font in scaledFonts.Values)
                    font.Dispose();
                scaledFonts.Clear();
                if (taglineFont != null)
                    taglineFont.Dispose();
                renderRunning = false;
                if (renderThread != null)
                {
                    renderThread.Join(500);
                    renderThread = null;
                }
                lock (headerSwap)
                {
                    if (headerFront != null) { headerFront.Dispose(); headerFront = null; }
                    if (headerBack != null) { headerBack.Dispose(); headerBack = null; }
                }
                rowBrush.Dispose();
                rowSelectedBrush.Dispose();
                light.Dispose();
                if (scaledBrand != null)
                    scaledBrand.Dispose();
                if (brand != null)
                    brand.Dispose();
                if (resizePreview != null)
                    resizePreview.Dispose();
                lock (overlayLock)
                {
                    if (headerOverlay != null) { headerOverlay.Dispose(); headerOverlay = null; }
                }
            }
            base.Dispose(disposing);
        }

        [DllImport("dwmapi.dll")]
        private static extern int DwmSetWindowAttribute(IntPtr window, int attribute, ref int value, int size);

        /// <summary>Ask the shell for a dark title bar. Attribute 20 on Windows 11 and later
        /// builds of 10, 19 on the first that supported it; both are ignored elsewhere.
        /// The update dialog uses it too, so the two windows match.</summary>
        internal static void UseDarkTitleBar(IntPtr handle)
        {
            int on = 1;
            try
            {
                if (DwmSetWindowAttribute(handle, 20, ref on, sizeof(int)) != 0)
                    DwmSetWindowAttribute(handle, 19, ref on, sizeof(int));
            }
            catch { }
        }

        [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)]
        private static extern int SetWindowTheme(IntPtr window, string application, string idList);

        /// <summary>Ask for the shell's dark scrollbars on a control that draws its own
        /// rows on a dark ground. Where the theme does not exist the light ones stay.</summary>
        internal static void UseDarkScrollBars(IntPtr handle)
        {
            try { SetWindowTheme(handle, "DarkMode_Explorer", null); }
            catch { }
        }


        /// <summary>Swap the card between the steps and the settings view, cross-fading.
        ///
        /// Both states are rendered to bitmaps and a FadeOverlay is laid over the card
        /// while the alpha runs down; the real controls are swapped underneath it before
        /// the animation starts, so when the overlay goes away the live view is already
        /// in place and there is no second repaint to see.
        ///
        /// About 160 ms, which is long enough to read as a transition and short enough
        /// that a user clicking the gear twice in a row does not queue up a wait. A
        /// second call while one is running finishes the first immediately rather than
        /// stacking overlays.</summary>
        private void ShowSettings(bool show)
        {
            // Already there, or already going there: do nothing. Without this, pressing
            // the button twice restarted the fade from the top and stacked a second
            // overlay on the first, which looked like a stutter and leaked a timer.
            if (show == settingsOpen)
                return;
            settingsOpen = show;
            // Advanced Settings opens at its first row every time.
            if (show)
                settingsScroll.ScrollTo(0F, true);

            // Any fade still running is finished instantly rather than cancelled, so the
            // control tree is in a settled state before the next capture.
            FinishFade();

            Bitmap outgoing = CaptureCard();
            ApplyViewState();
            Bitmap incoming = CaptureCard();

            if (outgoing == null || incoming == null)
            {
                if (outgoing != null) outgoing.Dispose();
                if (incoming != null) incoming.Dispose();
                return;
            }

            fadeOverlay = new FadeOverlay(outgoing, incoming);
            fadeOverlay.SetBounds(0, 0, mainCard.Width, mainCard.Height);
            mainCard.Controls.Add(fadeOverlay);
            fadeOverlay.BringToFront();

            const int stepMs = 16;
            const float perStep = stepMs / 160F;
            fadeTimer = new Timer();
            fadeTimer.Interval = stepMs;
            fadeTimer.Tick += delegate
            {
                if (fadeOverlay == null)
                {
                    FinishFade();
                    return;
                }
                fadeOverlay.Progress = fadeOverlay.Progress + perStep;
                if (fadeOverlay.Progress >= 1F)
                    FinishFade();
            };
            fadeTimer.Start();
        }

        /// <summary>Tear down any running cross-fade, leaving the live controls showing.
        /// Safe to call when none is running.</summary>
        private void FinishFade()
        {
            if (fadeTimer != null)
            {
                fadeTimer.Stop();
                fadeTimer.Dispose();
                fadeTimer = null;
            }
            if (fadeOverlay != null)
            {
                mainCard.Controls.Remove(fadeOverlay);
                fadeOverlay.Dispose();
                fadeOverlay = null;
            }
        }

        /// <summary>The card as it currently looks, or null if it cannot be rendered.
        /// DrawToBitmap fails on a control with no handle or a zero dimension, neither of
        /// which is worth aborting a view switch over.</summary>
        private Bitmap CaptureCard()
        {
            try
            {
                if (mainCard == null || mainCard.Width <= 0 || mainCard.Height <= 0)
                    return null;
                Bitmap shot = new Bitmap(mainCard.Width, mainCard.Height);
                mainCard.DrawToBitmap(shot, new Rectangle(0, 0, mainCard.Width, mainCard.Height));
                return shot;
            }
            catch { return null; }
        }

        private StepRow NewStep(CardPanel card, int index, UiTheme.Glyph icon, string title, string subtitle)
        {
            StepRow row = new StepRow();
            row.Icon = icon;
            row.Title = title;
            row.Subtitle = subtitle;
            row.SetBounds(0, index * 96, card.Width, 96);
            row.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            card.Controls.Add(row);
            return row;
        }

        private static StateLabel NewStateLabel(StepRow row, int cardWidth)
        {
            StateLabel label = new StateLabel();
            label.Font = UiTheme.DisplayFont(18F, FontStyle.Bold);
            label.ForeColor = UiTheme.TextMuted;
            // Tall enough for the icon-only badge; still centred on the header centre
            // line, so the text states sit exactly where they did.
            label.SetBounds(cardWidth - 340, 20, 300, 56);
            label.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            row.Controls.Add(label);
            return label;
        }

        private readonly SolidBrush rowBrush = new SolidBrush(UiTheme.Field);
        private readonly SolidBrush rowSelectedBrush = new SolidBrush(UiTheme.AccentDark);

        protected override void OnPaint(PaintEventArgs e)
        {
            if (resizePreviewActive && resizePreview != null)
            {
                e.Graphics.CompositingMode = CompositingMode.SourceCopy;
                e.Graphics.CompositingQuality = CompositingQuality.HighSpeed;
                e.Graphics.InterpolationMode = InterpolationMode.Bilinear;
                e.Graphics.PixelOffsetMode = PixelOffsetMode.HighSpeed;
                e.Graphics.DrawImage(resizePreview, ClientRectangle,
                    0, 0, resizePreview.Width, resizePreview.Height, GraphicsUnit.Pixel);

                // The snapshot exists because re-laying out the card's child controls on
                // every mouse move is expensive. The header has no child controls at all,
                // so it can be repainted live over the frozen frame: background, plume,
                // then the brand layer baked when the resize began. Stretching that layer
                // costs one bilinear blit, where rebuilding it would mean a bicubic
                // resample of the artwork per frame -- the thing the brand cache exists
                // to avoid.
                if (resizePreview.Height > 0)
                {
                    // An exception thrown out of a paint handler mid-drag would surface as
                    // a JIT dialog, so a failure here just leaves the plain frozen snapshot.
                    try
                    {
                        int headerNow = LiveHeaderHeight();
                        if (headerNow > 0)
                        {
                            Rectangle live = new Rectangle(0, 0, ClientSize.Width, headerNow);
                            GraphicsState held = e.Graphics.Save();
                            e.Graphics.SetClip(live);
                            BlitHeader(e.Graphics, live);
                            e.Graphics.Restore(held);
                        }
                    }
                    catch { }
                }
                return;
            }

            base.OnPaint(e);
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = TextRenderingHint.ClearTypeGridFit;

            // No gradient behind the header: the only fade in this area should be the
            // crest's own, baked into the artwork. A background ramp read as a second,
            // competing fade.

            // Drifting haze, painted first so it passes behind the crest and the wordmark
            // rather than over them. Clipped to the header strip: below it the card covers
            // everything anyway, so drawing there would only be wasted upscaling.
            Rectangle header = new Rectangle(0, 0, ClientSize.Width, ScaleDesign(headerHeight));
            EnsureHeaderOverlay(header.Width, header.Height);
            UpdatePresentMode();
            // The frame already contains the brand and tagline: the render thread composites
            // them, so a repaint here is one blit rather than a re-render of the lockup.
            BlitHeader(g, header);
        }

        /// <summary>The brand lockup and tagline, without the background or the plume.
        /// Split out so the resize path can bake exactly this into a transparent layer
        /// and composite it over live smoke.</summary>
        private void PaintBrandLayer(Graphics g, int clientWidth)
        {
            // The crest and the metallic wordmark are one baked lockup, so the crest's
            // fade lines up with the letters exactly as it was composed.
            int scaledBrandWidth = Math.Max(1, (int)Math.Round(brandWidth * uiScale));
            int scaledBrandHeight = Math.Max(1, (int)Math.Round(brandHeight * uiScale));
            int brandTop = Math.Max(1, (int)Math.Round(14 * uiScale));
            int taglineTop = Math.Max(1, (int)Math.Round(30 * uiScale));
            if (brand != null)
            {
                if (scaledBrand == null || scaledBrand.Width != scaledBrandWidth
                    || scaledBrand.Height != scaledBrandHeight)
                {
                    if (scaledBrand != null)
                        scaledBrand.Dispose();
                    scaledBrand = new Bitmap(scaledBrandWidth, scaledBrandHeight,
                        PixelFormat.Format32bppArgb);
                    using (Graphics bg = Graphics.FromImage(scaledBrand))
                    {
                        bg.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        bg.PixelOffsetMode = PixelOffsetMode.HighQuality;
                        bg.DrawImage(brand, 0, 0, scaledBrandWidth, scaledBrandHeight);
                    }
                }
                g.DrawImageUnscaled(scaledBrand, (clientWidth - scaledBrandWidth) / 2, brandTop);
                taglineTop = brandTop + scaledBrandHeight + Math.Max(1, (int)Math.Round(2 * uiScale));
            }

            // The tagline is set to the width of the wordmark's ink, not the width of the
            // brand image: the artwork carries transparent margin and glow past the last
            // letter, so matching the image would leave the tagline visibly wider.
            // GenericTypographic, not the default: the default format pads either side of
            // the string, so measuring with it makes the tagline come out ~3% narrow and
            // off-centre. Typographic reports the glyphs themselves.
            using (StringFormat sf = new StringFormat(StringFormat.GenericTypographic))
            using (SolidBrush ink = new SolidBrush(UiTheme.Accent))
            {
                sf.Alignment = StringAlignment.Center;
                sf.FormatFlags |= StringFormatFlags.NoWrap;

                if (taglineFont == null)
                {
                    double target = (WordmarkInkRight - WordmarkInkLeft) * scaledBrandWidth;
                    using (Font probe = new Font("Segoe UI", Math.Max(6F, 20F * uiScale), FontStyle.Bold))
                    {
                        float measured = g.MeasureString(Tagline, probe, Int32.MaxValue, sf).Width;
                        float size = measured > 1F
                            ? (float)(20.0 * uiScale * target / measured)
                            : 10.5F * uiScale;
                        taglineFont = new Font("Segoe UI", Math.Max(6F, size), FontStyle.Bold);
                    }
                }

                g.DrawString(Tagline, taglineFont, ink,
                    new RectangleF(0, taglineTop, clientWidth,
                        taglineFont.Height + Math.Max(2, (int)Math.Round(8 * uiScale))), sf);
            }
        }

        private void OpenCreatorPage()
        {
            try
            {
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = CreatorUrl;
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open the creator's page",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private bool updateCheckStarted;

        /// <summary>Ask GitHub for the latest release off the UI thread; if it is newer,
        /// offer it once the window is idle. See UpdateCheck.</summary>
        private void StartUpdateCheck()
        {
            System.Threading.Thread check = new System.Threading.Thread(delegate()
            {
                string latest = UpdateCheck.LatestVersion();
                if (latest == null || !UpdateCheck.IsNewer(latest, GoldPatch.PatchVersion))
                    return;
                try { BeginInvoke(new MethodInvoker(delegate { OfferUpdate(latest); })); }
                catch { }   // the window closed first
            });
            check.IsBackground = true;
            check.Start();
        }

        private void OfferUpdate(string latest)
        {
            // Never over a patch in progress, and not for a version the player skipped
            // -- though a version later than that one is offered again.
            if (IsDisposed || operationRunning)
                return;
            string skipped = KmrpSettings.SkippedUpdate;
            if (skipped.Length > 0 && !UpdateCheck.IsNewer(latest, skipped))
                return;
            using (UpdateDialog dialog = new UpdateDialog(latest, GoldPatch.PatchVersion, uiScale))
            {
                bool download = dialog.ShowDialog(this) == DialogResult.OK;
                // The switch counts however the dialog was left, Download included.
                if (dialog.DontRemind)
                    KmrpSettings.SkippedUpdate = latest;
                if (!download)
                    return;
            }
            try
            {
                ProcessStartInfo start = new ProcessStartInfo();
                start.FileName = UpdateCheck.DownloadPage;
                start.UseShellExecute = true;
                Process.Start(start);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open the download page",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        /// <summary>Where step 1 starts: swkotor.exe beside the patcher or in the current
        /// folder, as always; otherwise Steam's KOTOR, then GOG's, found as GameFolders
        /// finds them (2026-09-30, at the maintainer's request: "can we auto detect steam
        /// version if its there? cus macos can do that"). When none has one, the path
        /// beside the patcher, which step 2 reports as missing.</summary>
        private static string FindDefaultExecutable()
        {
            string besidePatcher = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "swkotor.exe");
            if (File.Exists(besidePatcher))
                return besidePatcher;
            string current = Path.Combine(Environment.CurrentDirectory, "swkotor.exe");
            if (File.Exists(current))
                return current;
            foreach (string folder in GameFolders.Installed())
            {
                string found = Path.Combine(folder, "swkotor.exe");
                if (File.Exists(found))
                    return found;
            }
            return besidePatcher;
        }

        private void BrowseForExecutable(IWin32Window owner)
        {
            using (OpenFileDialog dialog = new OpenFileDialog())
            {
                dialog.Title = "Select swkotor.exe in your KOTOR folder";
                dialog.Filter = "KOTOR executable (swkotor.exe)|swkotor.exe|Executable files (*.exe)|*.exe|All files (*.*)|*.*";
                if (File.Exists(pathBox.Text))
                    dialog.InitialDirectory = Path.GetDirectoryName(Path.GetFullPath(pathBox.Text));
                if (dialog.ShowDialog(owner) == DialogResult.OK)
                    pathBox.Text = dialog.FileName;
            }
        }

        private void SetState(StateLabel label, string text, Color color)
        {
            label.Badge = StateLabel.StatusBadge.None;
            label.Text = text;
            label.ForeColor = color;
        }

        /// <summary>Step 2: which swkotor.exe this is, in its subtitle and its state label,
        /// and steps 3 and 4 dimmed until it is one KMRP installs on.</summary>
        private void UpdateGameStep(ExecutableState state, string target, bool executableReady)
        {
            stepResolution.Dimmed = !executableReady;
            stepApply.Dimmed = !executableReady;
            GameExecutable exe = GameExecutable.Identify(target);
            if (executableReady)
            {
                SetState(verifyState, exe != null ? exe.Name : "Detected", UiTheme.Success);
                verifyState.Badge = StateLabel.StatusBadge.Verified;
                if (state == ExecutableState.Gold)
                    stepVerify.SetSubtitle(exe != null
                        ? "KOTOR Modern Restoration Patch detected, on the " + VersionName(exe) + "."
                        : "An earlier KOTOR Modern Restoration Patch detected.");
                else
                    stepVerify.SetSubtitle(exe == null ? "A supported swkotor.exe detected."
                        : exe == GameExecutable.Editable ? "The editable 1.03 swkotor.exe detected."
                        : "The " + VersionName(exe) + " of KOTOR detected.");
                return;
            }
            // The badge alone marks the step unsatisfied; the subtitle says which failure
            // it is.
            SetState(verifyState, String.Empty, state == ExecutableState.Error ? UiTheme.Error : UiTheme.Warning);
            verifyState.Badge = StateLabel.StatusBadge.Missing;
            if (state == ExecutableState.Missing)
                stepVerify.SetSubtitle("No swkotor.exe here. Choose your KOTOR folder in step 1.");
            else if (state == ExecutableState.Unsupported)
                stepVerify.SetSubtitle("This swkotor.exe is not the Steam, GOG or editable 1.03 version.");
            else
                stepVerify.SetSubtitle("This swkotor.exe could not be read.");
        }

        private static string VersionName(GameExecutable exe)
        {
            return exe == GameExecutable.Editable ? "editable 1.03 swkotor.exe" : exe.Name + " version";
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        internal struct DisplayMode
        {
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string DeviceName;
            public short SpecVersion, DriverVersion, StructSize, DriverExtra;
            public int Fields, PositionX, PositionY, DisplayOrientation, DisplayFixedOutput;
            public short ColorMode, Duplex, YResolution, TTOption, Collate;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)] public string FormName;
            public short LogPixels;
            public int BitsPerPel, PelsWidth, PelsHeight, DisplayFlags, DisplayFrequency;
            public int IcmMethod, IcmIntent, MediaType, DitherType, Reserved1, Reserved2, PanningWidth, PanningHeight;
        }

        internal const int EnumCurrentSettings = -1;

        [DllImport("user32.dll", CharSet = CharSet.Unicode, EntryPoint = "EnumDisplaySettingsW")]
        internal static extern bool EnumDisplaySettings(string deviceName, int modeNumber, ref DisplayMode mode);

        private void RefreshStatus()
        {
            if (actionButton == null || applyState == null)
                return;
            if (operationRunning)
                return;

            string target = pathBox.Text.Trim();
            ExecutableState state = PatchOperations.Inspect(target);
            bool iniExists = false;
            try { iniExists = File.Exists(IniOperations.PathForExecutable(target)); }
            catch { }

            string folder = null;
            try { folder = File.Exists(target) ? Path.GetDirectoryName(Path.GetFullPath(target)) : null; }
            catch { }
            stepFolder.SetSubtitle(String.IsNullOrEmpty(folder)
                ? "Choose your Knights of the Old Republic folder."
                : folder);

            bool executableReady = state == ExecutableState.SupportedClean || state == ExecutableState.Gold;
            actionIsRestore = PatchOperations.CanRestore(target);
            actionButton.Text = actionIsRestore ? "Restore Original" : "Start Patching";
            actionButton.Enabled = actionIsRestore || (executableReady && iniExists);
            // An installed KMRP older than this installer: Restore Original and Upgrade
            // side by side. The same build, or a newer one, keeps Restore Original alone,
            // so the window never installs an older build over a newer one (the
            // maintainer, 2026-10-19).
            int? age = actionIsRestore ? KpmEditionOperations.CompareInstalled(target) : null;
            bool upgrade = age == -1 && iniExists;
            upgradeButton.Enabled = upgrade;
            LayoutActionRow(upgrade);

            UpdateGameStep(state, target, executableReady);

            bool patchComplete = state == ExecutableState.Gold;
            stepFolder.SetTitle(patchComplete ? "1. Selected Game Folder" : "1. Select Game Folder");
            stepVerify.SetTitle(patchComplete ? "2. Detected Game Version" : "2. Detect Game Version");
            stepResolution.SetTitle("3. Resolutions");
            stepResolution.SetSubtitle(patchComplete
                ? "The game starts at this resolution. Choose another in the game's Graphics options."
                : ResolutionSelection.Summary());
            resolutionState.Visible = patchComplete;

            if (patchComplete)
            {
                int installedWidth;
                int installedHeight;
                if (PatchOperations.TryReadInstalledResolution(target, out installedWidth, out installedHeight))
                {
                    SetState(resolutionState,
                        installedWidth.ToString(CultureInfo.InvariantCulture) + " × " +
                        installedHeight.ToString(CultureInfo.InvariantCulture), UiTheme.Text);
                }
                else
                {
                    SetState(resolutionState, "Installed", UiTheme.Text);
                }
            }
            else
            {
                resolutionState.Text = String.Empty;
            }

            DateTimeOffset? installedBuild = KpmEditionOperations.InstalledBuild(target);
            if (state == ExecutableState.Gold && upgrade)
            {
                SetState(applyState, "Upgrade available", UiTheme.Accent);
                lastDetail = installedBuild.HasValue
                    ? "Installed: " + BuildStamp.Display(installedBuild.Value) + ". This build: " +
                      BuildStamp.Display(BuildStamp.Current.Value) + "."
                    : "An earlier KMRP is installed. This installer's build is newer.";
            }
            else if (state == ExecutableState.Gold && age == 1 && installedBuild.HasValue)
            {
                SetState(applyState, "Newer build installed", UiTheme.Warning);
                lastDetail = "A newer build is installed (" + BuildStamp.Display(installedBuild.Value) + ").";
            }
            else if (state == ExecutableState.Gold)
            {
                SetState(applyState, "Patched successfully", UiTheme.Success);
                int readyWidth;
                int readyHeight;
                if (KpmEditionOperations.IsInstalledForPatchManager(target))
                    lastDetail = "Managed by KOTOR Patch Manager: tick KMRP there, then Apply and Launch.";
                else
                    lastDetail = PatchOperations.TryReadInstalledResolution(target, out readyWidth, out readyHeight)
                        ? "KOTOR is ready to play at " +
                            readyWidth.ToString(CultureInfo.InvariantCulture) + " × " +
                            readyHeight.ToString(CultureInfo.InvariantCulture) + "."
                        : "KOTOR is ready to play.";
            }
            else if (executableReady && iniExists)
            {
                SetState(applyState, "Ready to patch", UiTheme.Accent);
                lastDetail = "Everything is ready. Start patching when ready.";
            }
            else if (executableReady)
            {
                SetState(applyState, "Game setup needed", UiTheme.Warning);
                lastDetail = "Launch KOTOR once, close it, then return here and check again.";
            }
            else
            {
                SetState(applyState, "Not patched", UiTheme.TextMuted);
                lastDetail = PatchOperations.Describe(target);
            }
            stepApply.SetSubtitle(lastDetail);

            // RefreshStatus decides what the *steps* look like, and says nothing about
            // which view is on screen. It runs on Activated, so without this the settings
            // view was thrown away every time the window regained focus -- click another
            // window, come back, and the main page had returned underneath you.
            ApplyViewState();
        }

        /// <summary>Make the current view match `settingsOpen`.
        ///
        /// The single place that decides which of the two views is visible, so no other
        /// code has to remember. Only the card's direct children are touched: everything
        /// RefreshStatus toggles lives inside a step row and is hidden with its parent.</summary>
        private void ApplyViewState()
        {
            if (settingsView == null)
                return;   // still constructing
            for (int i = 0; i < mainViewControls.Count; i++)
                mainViewControls[i].Visible = !settingsOpen;
            upgradeButton.Visible = !settingsOpen && upgradeOffered;
            settingsView.Visible = settingsOpen;
        }

        /// <summary>The action row: one button across the primary's place, or, with
        /// `split`, Restore Original and Upgrade sharing it at one size, a gap between them
        /// as wide as the one before the settings button, which does not move. The
        /// rectangles are set as design rectangles, which every resize scales
        /// (ApplyUniformScale), and applied at the scale in use.</summary>
        private void LayoutActionRow(bool split)
        {
            if (actionRowDesign.IsEmpty && !designBounds.TryGetValue(actionButton, out actionRowDesign))
                return;   // still constructing
            Rectangle settingsDesign;
            int gap = designBounds.TryGetValue(settingsButton, out settingsDesign)
                ? settingsDesign.Left - actionRowDesign.Right : 12;
            Rectangle first = actionRowDesign;
            Rectangle second = actionRowDesign;
            if (split)
            {
                first.Width = (actionRowDesign.Width - gap) / 2;
                second.X = first.Right + gap;
                second.Width = actionRowDesign.Right - second.X;
            }
            upgradeOffered = split;
            actionButton.Primary = !split;
            actionButton.Invalidate();
            PlaceDesign(actionButton, first);
            PlaceDesign(upgradeButton, second);
            upgradeButton.Visible = split && !settingsOpen;
        }

        private void PlaceDesign(Control control, Rectangle logical)
        {
            designBounds[control] = logical;
            control.SetBounds((int)Math.Round(logical.X * uiScale), (int)Math.Round(logical.Y * uiScale),
                Math.Max(1, (int)Math.Round(logical.Width * uiScale)),
                Math.Max(1, (int)Math.Round(logical.Height * uiScale)));
        }

        private void UpgradeClicked(object sender, EventArgs e)
        {
            PatchClicked(sender, e, "Upgrade");
        }

        private void ActionClicked(object sender, EventArgs e)
        {
            if (actionIsRestore)
                RestoreClicked(sender, e);
            else
                PatchClicked(sender, e);
        }

        private void PatchClicked(object sender, EventArgs e)
        {
            PatchClicked(sender, e, "Patch");
        }

        /// <summary>An install, "Patch" on a clean game or "Upgrade" over an older KMRP:
        /// the same operation, which takes the earlier install away and installs with the
        /// settings chosen now (KpmEditionOperations.Install).</summary>
        private void PatchClicked(object sender, EventArgs e, string name)
        {
            // The display's current size, where the game will offer it.
            int[] start = ResolutionSelection.Start();
            if (start == null)
            {
                MessageBox.Show(this, "This display reports no resolution KMRP can use.", "Resolution required",
                    MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            RunOperation(name, delegate(Action<string> report, Action<int, string> progress)
            {
                PatchOperations.ApplyInPlace(pathBox.Text.Trim(), start[0], start[1], report, progress);
            });
        }

        private void RestoreClicked(object sender, EventArgs e)
        {
            RunOperation("Restore", delegate(Action<string> report, Action<int, string> progress)
            {
                PatchOperations.Restore(pathBox.Text.Trim(), report, progress);
            });
        }

        private void RunOperation(string name, UiOperation operation)
        {
            if (operationRunning)
                return;

            string target = pathBox.Text.Trim();
            bool installing = name != "Restore";
            // The row is one button while anything runs: its progress fills it.
            LayoutActionRow(false);
            actionButton.ProgressPercent = 0;
            actionButton.Text = name == "Upgrade" ? "Preparing upgrade…   0%"
                : installing ? "Preparing patch…   0%" : "Preparing restore…   0%";
            operationRunning = true;
            SetBusyState(true);
            SetState(applyState, name == "Upgrade" ? "Upgrading…" : installing ? "Patching…" : "Restoring…", UiTheme.Accent);
            stepApply.SetSubtitle(installing
                ? "KMRP is updating your game. Please wait."
                : "KMRP is restoring your original files. Please wait.");

            BackgroundWorker worker = new BackgroundWorker();
            worker.WorkerReportsProgress = true;
            worker.DoWork += delegate(object sender, DoWorkEventArgs e)
            {
                string result = null;
                operation(
                    delegate(string message)
                    {
                        result = message;
                        try { PatchOperations.AppendLog(target, name + ": " + message); }
                        catch { }
                    },
                    delegate(int percent, string message)
                    {
                        worker.ReportProgress(Math.Max(0, Math.Min(100, percent)), message);
                    });
                e.Result = result;
            };
            worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs e)
            {
                int percent = Math.Max(0, Math.Min(100, e.ProgressPercentage));
                actionButton.ProgressPercent = percent;
                // "what is being done", then after a tab the time left, which is shown under
                // the button (timeLeftLabel).
                string message = e.UserState as string ?? String.Empty;
                int tab = message.IndexOf('\t');
                string left = tab >= 0 ? message.Substring(tab + 1) : String.Empty;
                if (tab >= 0)
                    message = message.Substring(0, tab);
                actionButton.Text = (String.IsNullOrWhiteSpace(message) ? "Working…" : message) +
                    "   " + percent.ToString(CultureInfo.InvariantCulture) + "%";
                timeLeftLabel.Text = left;
                timeLeftLabel.Visible = left.Length > 0;
            };
            worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e)
            {
                actionButton.ProgressPercent = -1;
                timeLeftLabel.Visible = false;
                timeLeftLabel.Text = String.Empty;
                operationRunning = false;
                SetBusyState(false);

                if (e.Error != null)
                {
                    RefreshStatus();
                    SetState(applyState, "Error", UiTheme.Error);
                    stepApply.SetSubtitle(name + " stopped — no incomplete changes were left behind.");
                    try { PatchOperations.AppendLog(target, name + " failed: " + e.Error); } catch { }
                    MessageBox.Show(this, e.Error.Message, name + " blocked", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return;
                }

                string result = e.Result as string;
                RefreshStatus();
                SetState(applyState, name == "Upgrade" ? "Upgraded successfully"
                    : installing ? "Patched successfully" : "Restored successfully", UiTheme.Success);
                // The step has one line. `result` is the operation's last message, which
                // for an install is whichever sentence came last, the one about KOTOR
                // Patch Manager's patch folder with its whole path among them: it ran
                // under the state on the right and was cut off (the maintainer saw it on
                // 2026-10-09, "step 4 gets mangled"). A message that fits is shown; a
                // longer one stays in the log (Open Log), and the step says what
                // RefreshStatus found, "KOTOR is ready to play at W × H."
                stepApply.SetSubtitle(result == null ? name + " completed."
                    : result.Length <= StepLineLimit ? result : lastDetail);
                if (installing)
                    OfferSteamLayout(target);
            };
            worker.RunWorkerAsync();
        }

        /// <summary>After an install under Wine or Proton with Controller Support on:
        /// Steam's controller layout for KOTOR has to be the Gamepad one. Steam's
        /// default layout for the game sends keyboard and mouse, the game being listed
        /// without controller support, and KMRP's controller support then gets no pad
        /// at all (SteamOS, Proton 11, 2026-10-12: "Controller 0 mapping uses xinput :
        /// false" until the layout was changed to the Gamepad template). Steam Input is
        /// always on there; on Windows it is off for an Xbox pad unless the player
        /// turned it on, so nothing is said on Windows. Told, not done: nothing of
        /// Steam's is written or opened here.</summary>
        private void OfferSteamLayout(string target)
        {
            if (!GameFolders.UnderWine() || !KmrpSettings.ControllerSupport)
                return;
            const string notice = "For the controller to work, KOTOR's controller layout in Steam has to be " +
                "set to Gamepad.\n\nSteam gives KOTOR a keyboard and mouse layout by default, and the game " +
                "then gets no controller at all.\n\nIn Steam: KOTOR -> the controller icon -> Edit Layout -> " +
                "Templates -> Gamepad -> Apply.";
            try
            {
                PatchOperations.AppendLog(target, "Controller under Steam on Linux: " +
                    notice.Replace("\n\n", " "));
                MessageBox.Show(this, notice, "Set the controller layout to Gamepad in Steam",
                    MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            catch { }
        }

        private void SetBusyState(bool busy)
        {
            browseButton.Enabled = !busy;
            actionButton.Enabled = !busy;
            upgradeButton.Enabled = !busy;
            logLink.Enabled = !busy;
            UseWaitCursor = busy;
        }

        private void OpenLogClicked(object sender, LinkLabelLinkClickedEventArgs e)
        {
            try
            {
                string logPath = PatchOperations.LogPath(pathBox.Text.Trim());
                if (!File.Exists(logPath))
                    File.WriteAllText(logPath, AppName + " log\r\n", new UTF8Encoding(false));
                Process.Start(logPath);
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, ex.Message, "Unable to open log", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    /// <summary>Where Steam and GOG installed KOTOR, for the patcher's first step: Steam's
    /// first, as the Mac installer finds it (macos/kmrp-mac.sh, find_game: every Steam
    /// library's steamapps\common\swkotor), then GOG's. Read from the registry and Steam's
    /// own files only; nothing is searched. Every source is optional, and a missing or
    /// unreadable one is skipped.</summary>
    internal static class GameFolders
    {
        // KOTOR's Steam app and GOG product ids.
        private const string SteamAppId = "32370";
        private const string GogGameId = "1207666283";

        /// <summary>The folders, Steam's before GOG's, each once, whether or not
        /// swkotor.exe is still there.</summary>
        internal static List<string> Installed()
        {
            List<string> folders = new List<string>();
            foreach (string folder in Wine())
                AddOnce(folders, folder);
            foreach (string folder in Steam())
                AddOnce(folders, folder);
            foreach (string folder in Gog())
                AddOnce(folders, folder);
            return folders;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        private static extern IntPtr GetModuleHandleW(string name);

        [DllImport("kernel32.dll", CharSet = CharSet.Ansi, ExactSpelling = true)]
        private static extern IntPtr GetProcAddress(IntPtr module, string name);

        /// <summary>Whether this is Wine (Proton included), by the export its ntdll.dll
        /// has for the purpose.</summary>
        internal static bool UnderWine()
        {
            try
            {
                IntPtr ntdll = GetModuleHandleW("ntdll.dll");
                return ntdll != IntPtr.Zero && GetProcAddress(ntdll, "wine_get_version") != IntPtr.Zero;
            }
            catch
            {
                return false;
            }
        }

        /// <summary>A Linux path as Wine shows it, on the Z: drive every Wine and Proton
        /// prefix maps to "/"; any other path as it is.</summary>
        private static string FromUnix(string path)
        {
            if (String.IsNullOrWhiteSpace(path) || !path.Trim().StartsWith("/", StringComparison.Ordinal))
                return path;
            return "Z:" + path.Trim().Replace('/', '\\');
        }

        /// <summary>Steam's KOTOR under Wine and Proton, where the registry is the
        /// prefix's and names no real Steam folder (issue 30: until 2026-10-10 the game
        /// was found there only with the installer in its folder). None of this is read
        /// on Windows. In order: the game folder Steam names to what it starts under
        /// Proton (STEAM_COMPAT_INSTALL_PATH); steamapps\common\swkotor at the root of
        /// each drive, since Proton maps the game's Steam library to a drive of its own
        /// (S:, measured on SteamOS 3.8.14, 2026-10-11); then the libraries Linux's Steam
        /// lists, from the folders it installs to under each home folder.</summary>
        private static List<string> Wine()
        {
            List<string> folders = new List<string>();
            if (!UnderWine())
                return folders;
            try
            {
                AddOnce(folders, FromUnix(Environment.GetEnvironmentVariable("STEAM_COMPAT_INSTALL_PATH")));
                foreach (string drive in Environment.GetLogicalDrives())
                    if (!drive.StartsWith("Z", StringComparison.OrdinalIgnoreCase))
                        AddOnce(folders, Path.Combine(drive, "steamapps", "common", "swkotor"));

                List<string> homes = new List<string>();
                AddOnce(homes, FromUnix(Environment.GetEnvironmentVariable("HOME")));
                try
                {
                    if (Directory.Exists(@"Z:\home"))
                        foreach (string home in Directory.GetDirectories(@"Z:\home"))
                            AddOnce(homes, home);
                }
                catch { }
                List<string> roots = new List<string>();
                AddOnce(roots, FromUnix(Environment.GetEnvironmentVariable("STEAM_COMPAT_CLIENT_INSTALL_PATH")));
                foreach (string home in homes)
                    foreach (string steam in new[] { @".local\share\Steam", @".steam\steam", @".steam\root",
                                 @".var\app\com.valvesoftware.Steam\.local\share\Steam",
                                 @"snap\steam\common\.local\share\Steam" })
                        AddOnce(roots, Path.Combine(home, steam));
                foreach (string folder in InLibraries(roots))
                    AddOnce(folders, folder);
            }
            catch { }
            return folders;
        }

        /// <summary>Steam's own record of the install (its uninstall entry for app 32370),
        /// then each library Steam lists in steamapps\libraryfolders.vdf, at the folder
        /// its appmanifest names (steamapps\common\swkotor unless it says otherwise).</summary>
        private static List<string> Steam()
        {
            List<string> folders = new List<string>();
            AddOnce(folders, ReadValue(Registry.LocalMachine,
                @"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App " + SteamAppId, "InstallLocation"));
            List<string> roots = new List<string>();
            AddOnce(roots, ReadValue(Registry.CurrentUser, @"Software\Valve\Steam", "SteamPath"));
            AddOnce(roots, ReadValue(Registry.LocalMachine, @"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"));
            AddOnce(roots, ReadValue(Registry.LocalMachine, @"SOFTWARE\Valve\Steam", "InstallPath"));
            foreach (string folder in InLibraries(roots))
                AddOnce(folders, folder);
            return folders;
        }

        /// <summary>KOTOR's folder in each Steam folder given and in each library its
        /// steamapps\libraryfolders.vdf lists, whether or not the game is there. Linux's
        /// Steam lists Linux paths, read through Z: (FromUnix).</summary>
        private static List<string> InLibraries(List<string> roots)
        {
            List<string> folders = new List<string>();
            List<string> libraries = new List<string>();
            foreach (string root in roots)
            {
                AddOnce(libraries, root);
                try
                {
                    string list = Path.Combine(root, "steamapps", "libraryfolders.vdf");
                    if (File.Exists(list))
                        foreach (Match path in Regex.Matches(File.ReadAllText(list),
                                     "\"path\"\\s+\"([^\"]+)\"", RegexOptions.CultureInvariant))
                            AddOnce(libraries, FromUnix(path.Groups[1].Value.Replace("\\\\", "\\")));
                }
                catch { }
            }
            foreach (string library in libraries)
            {
                string installDir = "swkotor";
                try
                {
                    string manifest = Path.Combine(library, "steamapps", "appmanifest_" + SteamAppId + ".acf");
                    if (File.Exists(manifest))
                    {
                        Match named = Regex.Match(File.ReadAllText(manifest),
                            "\"installdir\"\\s+\"([^\"]+)\"", RegexOptions.CultureInvariant);
                        if (named.Success)
                            installDir = named.Groups[1].Value;
                    }
                }
                catch { }
                AddOnce(folders, Path.Combine(library, "steamapps", "common", installDir));
            }
            return folders;
        }

        /// <summary>GOG Galaxy's and GOG's installers' record of the game.</summary>
        private static List<string> Gog()
        {
            List<string> folders = new List<string>();
            AddOnce(folders, ReadValue(Registry.LocalMachine, @"SOFTWARE\WOW6432Node\GOG.com\Games\" + GogGameId, "path"));
            AddOnce(folders, ReadValue(Registry.LocalMachine, @"SOFTWARE\GOG.com\Games\" + GogGameId, "path"));
            return folders;
        }

        /// <summary>A value of the registry, or null. HKEY_LOCAL_MACHINE in both of its
        /// views, the 64-bit one first: the installer is a 32-bit program since 2026-10-19
        /// (ArtPreparation, KpmEdition.cs), which Windows otherwise shows only the 32-bit
        /// view, and an uninstall entry or a store's record may be in either.</summary>
        private static string ReadValue(RegistryKey hive, string key, string name)
        {
            if (hive == Registry.LocalMachine && Environment.Is64BitOperatingSystem)
            {
                foreach (RegistryView view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
                {
                    try
                    {
                        using (RegistryKey root = RegistryKey.OpenBaseKey(RegistryHive.LocalMachine, view))
                        using (RegistryKey opened = root.OpenSubKey(key))
                        {
                            string value = opened == null ? null : opened.GetValue(name) as string;
                            if (value != null)
                                return value;
                        }
                    }
                    catch { }
                }
                return null;
            }
            try
            {
                using (RegistryKey opened = hive.OpenSubKey(key))
                    return opened == null ? null : opened.GetValue(name) as string;
            }
            catch
            {
                return null;
            }
        }

        /// <summary>A folder, with Steam's forward slashes turned round, unless it is
        /// empty or already listed.</summary>
        private static void AddOnce(List<string> folders, string folder)
        {
            if (String.IsNullOrWhiteSpace(folder))
                return;
            string normal;
            try
            {
                normal = Path.GetFullPath(folder.Trim().Replace('/', '\\')).TrimEnd('\\');
            }
            catch
            {
                return;
            }
            foreach (string listed in folders)
                if (String.Equals(listed, normal, StringComparison.OrdinalIgnoreCase))
                    return;
            folders.Add(normal);
        }
    }

    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 3 && args[0] == "--apply")
                {
                    PatchOperations.ApplyToNewFile(args[1], args[2], 3440, 1440);
                    return 0;
                }
                if (args.Length == 4 && args[0] == "--apply")
                {
                    int width;
                    int height;
                    ParseResolution(args[3], out width, out height);
                    PatchOperations.ApplyToNewFile(args[1], args[2], width, height);
                    return 0;
                }
                if (args.Length == 2 && args[0] == "--in-place")
                {
                    PatchOperations.ApplyInPlace(args[1], delegate { });
                    return 0;
                }
                if (args.Length == 3 && args[0] == "--in-place")
                {
                    int width;
                    int height;
                    ParseResolution(args[2], out width, out height);
                    PatchOperations.ApplyInPlace(args[1], width, height, delegate { });
                    return 0;
                }
                if (args.Length == 2 && args[0] == "--restore")
                {
                    PatchOperations.Restore(args[1], delegate { });
                    return 0;
                }
                // KMRP's .kpatch file, its README and KPM's licence, for
                // sharing them on their own; the installer carries them since 2026-09-29.
                if (args.Length == 2 && args[0] == "--export-kpm-patches")
                {
                    KpmEditionOperations.ExportKpatches(args[1]);
                    return 0;
                }
                // Test-only (Test-GuiBlendHelper.py): the menus for a size as the install
                // blends them, with macos/tools/kmrp-guiblend's arguments -- the table,
                // the size, where to write, and a folder holding the set's files it
                // reads -- so the two can be compared byte for byte, and its exit codes:
                // 1 below 640x480, 2 when the sets do not reach the size.
                if (args.Length == 6 && args[0] == "--derive-gui")
                {
                    GuiBlend table = GuiBlend.Read(File.ReadAllBytes(args[1]));
                    int width = Int32.Parse(args[2], CultureInfo.InvariantCulture);
                    int height = Int32.Parse(args[3], CultureInfo.InvariantCulture);
                    if (width < GuiBlend.MinimumWidth || height < GuiBlend.MinimumHeight)
                        return 1;
                    if (!table.Covers(width, height))
                        return 2;
                    string setDirectory = args[5];
                    Directory.CreateDirectory(args[4]);
                    foreach (KeyValuePair<string, byte[]> file in table.Derive(width, height,
                        delegate(string name) { return GuiBlend.Text(File.ReadAllBytes(Path.Combine(setDirectory, name))); }))
                        File.WriteAllBytes(Path.Combine(args[4], file.Key), file.Value);
                    return 0;
                }
                // The installer's own workers, which make KMRP's art of every size before the
                // game first starts (ArtPreparation, KpmEdition.cs): the module's copy, the
                // game's folder, this worker's share and how many there are.
                if (args.Length == 5 && args[0] == ArtPreparation.WorkerSwitch)
                    return ArtPreparation.Worker(args[1], args[2],
                        Int32.Parse(args[3], CultureInfo.InvariantCulture), Int32.Parse(args[4], CultureInfo.InvariantCulture));
                if (args.Length != 0)
                    return 64;

                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new MainForm());
                return 0;
            }
            catch (Exception ex)
            {
                // Log startup failures for the window too, not just the CLI -- a GUI that
                // exits with code 1 and no trace is impossible to diagnose.
                try
                {
                    File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,
                        "KMRP.startup-error.log"), ex.ToString(), new UTF8Encoding(false));
                }
                catch { }
                if (args == null || args.Length == 0)
                {
                    try
                    {
                        MessageBox.Show(ex.ToString(), "KMRP could not start",
                            MessageBoxButtons.OK, MessageBoxIcon.Error);
                    }
                    catch { }
                }
                return 1;
            }
        }

        private static void ParseResolution(string value, out int width, out int height)
        {
            width = 0;
            height = 0;
            Match match = Regex.Match(value ?? String.Empty, "^(\\d+)[xX](\\d+)$",
                RegexOptions.CultureInvariant);
            if (!match.Success ||
                !Int32.TryParse(match.Groups[1].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out width) ||
                !Int32.TryParse(match.Groups[2].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out height))
                throw new ArgumentException("Resolution must use WIDTHxHEIGHT, for example 3440x1440.");
            ResolutionCatalog.Find(width, height);
        }
    }
}
