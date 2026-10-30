// Self-test for NvidiaPresentOperations, compiled together with the patcher source by
// Test-NvidiaPresentMethod.ps1 so it exercises exactly the code the patcher ships.
//
// Since 2026-10-30 KMRP sets no NVIDIA present method (its module draws each frame
// offscreen, K1OffscreenFrame.cpp); what is left is removing the Prefer native older KMRP
// installs set, which every install and restore now does. So each case below plants what
// an older install left (the value in the game's profile and KMRP's record of it) on a
// throwaway executable, and checks what Restore does with it.
//
//   describe <exe>   read-only: what NVIDIA applies to that executable
//   restore <exe>    the installer's own Restore, on that executable
//   cycle <dir>      the cases, on a throwaway executable named kmrp-nvapi-selftest.exe in
//                    <dir>, so no real game's profile is ever written
//
// Exit codes: 0 pass, 1 fail, 2 not applicable (no NVIDIA driver), 3 blocked (a profile
// with KMRP's name already exists).
using System;
using System.IO;
using System.Text;

namespace Kmrp
{
    internal static class NvidiaPresentSelfTest
    {
        private const uint PresentMethodId = 0x20D690F8;
        private const uint PreferNative = 0, PreferLayered = 1;
        // NVIDIA ships a profile that already names swkotor.exe; a throwaway profile stands in.
        private const string StandInProfile = "KMRP self-test stand-in profile";
        private static int failures;

        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 2 && args[0] == "restore")
                {
                    NvidiaPresentOperations.Restore(args[1], Console.WriteLine);
                    return File.Exists(Record(args[1])) ? 1 : 0;
                }
                if (args.Length == 2 && args[0] == "describe")
                {
                    Console.WriteLine(NvidiaPresentOperations.Describe(args[1]));
                    return 0;
                }
                if (args.Length == 2 && args[0] == "cycle")
                {
                    Directory.CreateDirectory(args[1]);
                    string exe = Path.Combine(args[1], "kmrp-nvapi-selftest.exe");
                    File.WriteAllBytes(exe, new byte[0]);
                    try
                    {
                        string before = NvidiaPresentOperations.Describe(exe);
                        Console.WriteLine("before:   " + before);
                        if (before.StartsWith("NVIDIA: unavailable", StringComparison.Ordinal))
                            return 2;
                        Expect(before.IndexOf("no profile names it", StringComparison.Ordinal) >= 0,
                            "the throwaway executable starts with no profile");
                        // The cases make and remove a profile of KMRP's name; one already there
                        // (an older install's, or a run that was stopped) is not the test's to
                        // delete. Seen on the maintainer's PC on 2026-10-30: NvAPI refused the
                        // name with -164, NVAPI_PROFILE_NAME_IN_USE.
                        bool taken = false;
                        WithSession(delegate(NvDrsSession drs)
                        {
                            taken = drs.FindProfile(NvidiaPresentOperations.ProfileName) != IntPtr.Zero;
                        });
                        if (taken)
                        {
                            Console.WriteLine("BLOCKED a profile named \"" + NvidiaPresentOperations.ProfileName +
                                "\" already exists. The test needs that name and does not delete a profile it did " +
                                "not make. Delete it in NVIDIA Control Panel (Manage 3D settings, Program Settings) " +
                                "or with NVIDIA Profile Inspector, then run the test again.");
                            return 3;
                        }
                        CreatedProfile(exe);
                        ExistingProfile(exe);
                        ChangedSince(exe);
                        SharedSince(exe);
                        NoRecord(exe);
                        ForeignProfileName(exe);
                    }
                    finally
                    {
                        File.Delete(exe);
                        string record = Record(exe);
                        if (File.Exists(record)) File.Delete(record);
                    }
                    Console.WriteLine(failures == 0 ? "PASS" : "FAIL " + failures);
                    return failures == 0 ? 0 : 1;
                }
                Console.WriteLine("usage: describe <exe> | restore <exe> | cycle <dir>");
                return 64;
            }
            catch (Exception ex)
            {
                Console.WriteLine("ERROR " + ex);
                return 1;
            }
        }

        // Where an older install wrote its record: the installer's own rule (KmrpFolder).
        private static string Record(string exe)
        {
            return KmrpFolder.PathOf(Path.GetFullPath(exe), KmrpFolder.NvidiaManifest);
        }

        // What an older install wrote: the record, in its format ("KMRPNV1", the path as
        // base64 of its UTF-8, whether KMRP made the profile).
        private static void WriteRecord(string exe, bool createdProfile)
        {
            string path = Record(exe);
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            File.WriteAllText(path, "KMRPNV1\r\n" +
                Convert.ToBase64String(Encoding.UTF8.GetBytes(Path.GetFullPath(exe))) + "\r\n" +
                (createdProfile ? "1" : "0") + "\r\n", new UTF8Encoding(false));
        }

        private static void Report(string message)
        {
            Console.WriteLine("report:   " + message);
        }

        private static void CreatedProfile(string exe)
        {
            Console.WriteLine("-- an older install made KMRP's profile");
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.CreateProfile(NvidiaPresentOperations.ProfileName);
                drs.AddApplication(profile, Path.GetFileName(exe));
                drs.SetDword(profile, PresentMethodId, PreferNative);
            });
            WriteRecord(exe, true);
            try
            {
                NvidiaPresentOperations.Restore(exe, Report);
                string after = NvidiaPresentOperations.Describe(exe);
                Console.WriteLine("after:    " + after);
                Expect(after.IndexOf("no profile names it", StringComparison.Ordinal) >= 0, "KMRP's profile is removed");
                Expect(!File.Exists(Record(exe)), "the record is removed");
            }
            finally { DeleteProfile(NvidiaPresentOperations.ProfileName); }
        }

        private static void ExistingProfile(string exe)
        {
            Console.WriteLine("-- an older install set the value in an existing profile");
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.CreateProfile(StandInProfile);
                drs.AddApplication(profile, Path.GetFileName(exe));
                drs.SetDword(profile, PresentMethodId, PreferNative);
            });
            WriteRecord(exe, false);
            try
            {
                NvidiaPresentOperations.Restore(exe, Report);
                string after = NvidiaPresentOperations.Describe(exe);
                Console.WriteLine("after:    " + after);
                Expect(after.IndexOf("profile \"" + StandInProfile + "\"", StringComparison.Ordinal) >= 0,
                    "the existing profile is kept");
                Expect(after.IndexOf("from the global profile", StringComparison.Ordinal) >= 0 ||
                       after.IndexOf("not set anywhere", StringComparison.Ordinal) >= 0,
                    "only KMRP's value is removed, so the game inherits again");
                Expect(!File.Exists(Record(exe)), "the record is removed");
            }
            finally { DeleteProfile(StandInProfile); }
        }

        private static void ChangedSince(string exe)
        {
            Console.WriteLine("-- the player changed the value after the older install");
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.CreateProfile(StandInProfile);
                drs.AddApplication(profile, Path.GetFileName(exe));
                drs.SetDword(profile, PresentMethodId, PreferLayered);
            });
            WriteRecord(exe, false);
            try
            {
                NvidiaPresentOperations.Restore(exe, Report);
                string after = NvidiaPresentOperations.Describe(exe);
                Console.WriteLine("after:    " + after);
                Expect(after.IndexOf("Prefer layered on DXGI Swapchain from the game's own profile", StringComparison.Ordinal) >= 0,
                    "the player's value is left");
                Expect(!File.Exists(Record(exe)), "the stale record is removed");
            }
            finally { DeleteProfile(StandInProfile); }
        }

        private static void SharedSince(string exe)
        {
            Console.WriteLine("-- KMRP's profile gained another application after the older install");
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.CreateProfile(NvidiaPresentOperations.ProfileName);
                drs.AddApplication(profile, Path.GetFileName(exe));
                drs.AddApplication(profile, "kmrp-nvapi-selftest-shared.exe");
                drs.SetDword(profile, PresentMethodId, PreferNative);
            });
            WriteRecord(exe, true);
            try
            {
                NvidiaPresentOperations.Restore(exe, Report);
                WithSession(delegate(NvDrsSession drs)
                {
                    IntPtr profile = drs.FindApplicationProfile(exe);
                    Expect(profile != IntPtr.Zero, "a profile that became shared is kept");
                    if (profile == IntPtr.Zero) return;
                    string name; int applications, settings;
                    drs.ProfileInfo(profile, out name, out applications, out settings);
                    Expect(applications == 2, "both applications are kept");
                    uint value; int location;
                    drs.TryGetDword(profile, PresentMethodId, out value, out location);
                    Expect(location != NvDrsSession.LocationCurrentProfile, "only KMRP's value is removed");
                });
            }
            finally { DeleteProfile(NvidiaPresentOperations.ProfileName); }
        }

        private static void NoRecord(string exe)
        {
            Console.WriteLine("-- Prefer native with no record of KMRP's (the player's own)");
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.CreateProfile(StandInProfile);
                drs.AddApplication(profile, Path.GetFileName(exe));
                drs.SetDword(profile, PresentMethodId, PreferNative);
            });
            try
            {
                NvidiaPresentOperations.Restore(exe, Report);
                string after = NvidiaPresentOperations.Describe(exe);
                Console.WriteLine("after:    " + after);
                Expect(after.IndexOf("Prefer native from the game's own profile", StringComparison.Ordinal) >= 0,
                    "a value KMRP has no record of is left");
            }
            finally { DeleteProfile(StandInProfile); }
        }

        private static void ForeignProfileName(string exe)
        {
            Console.WriteLine("-- a profile with KMRP's name that does not hold the game");
            bool made = false;
            try
            {
                WithSession(delegate(NvDrsSession drs)
                {
                    if (drs.FindProfile(NvidiaPresentOperations.ProfileName) != IntPtr.Zero)
                        throw new InvalidOperationException("Refusing to overwrite an existing profile in the test.");
                    IntPtr profile = drs.CreateProfile(NvidiaPresentOperations.ProfileName);
                    drs.AddApplication(profile, "kmrp-nvapi-selftest-foreign.exe");
                    drs.SetDword(profile, PresentMethodId, PreferNative);
                });
                made = true;
                WriteRecord(exe, true);
                NvidiaPresentOperations.Restore(exe, Report);
                WithSession(delegate(NvDrsSession drs)
                {
                    IntPtr profile = drs.FindProfile(NvidiaPresentOperations.ProfileName);
                    Expect(profile != IntPtr.Zero, "the foreign profile is kept");
                    if (profile == IntPtr.Zero) return;
                    string name; int applications, settings;
                    drs.ProfileInfo(profile, out name, out applications, out settings);
                    uint value; int location;
                    drs.TryGetDword(profile, PresentMethodId, out value, out location);
                    Expect(applications == 1 && value == PreferNative && location == NvDrsSession.LocationCurrentProfile,
                        "its application and setting are left intact");
                });
            }
            finally
            {
                if (made) DeleteProfile(NvidiaPresentOperations.ProfileName);
                string record = Record(exe);
                if (File.Exists(record)) File.Delete(record);
            }
        }

        private static void DeleteProfile(string name)
        {
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.FindProfile(name);
                if (profile != IntPtr.Zero)
                    drs.DeleteProfile(profile);
            });
        }

        private static void WithSession(Action<NvDrsSession> work)
        {
            string unavailable;
            using (NvDrsSession drs = NvDrsSession.TryOpen(out unavailable))
            {
                if (drs == null)
                    throw new InvalidOperationException("NVIDIA: " + unavailable);
                work(drs);
                int saved = drs.Save();
                if (saved != NvDrsSession.Ok)
                    throw new IOException("NvAPI_DRS_SaveSettings returned " + saved);
            }
        }

        private static void Expect(bool condition, string what)
        {
            Console.WriteLine((condition ? "  ok      " : "  FAILED  ") + what);
            if (!condition)
                failures++;
        }
    }
}
