// Self-test for NvidiaPresentOperations, compiled together with the patcher source by
// Test-NvidiaPresentMethod.ps1 so it exercises exactly the code the patcher ships.
//
//   describe <exe>   read-only: what NVIDIA applies to that executable
//   cycle <dir>      install -> verify -> restore -> verify, on a throwaway executable
//                    named kmrp-nvapi-selftest.exe in <dir>, so no real game's profile
//                    is ever written
//
// Exit codes: 0 pass, 1 fail, 2 not applicable (no NVIDIA driver, or its global
// present method is not "Prefer layered", so Install has nothing to do).
using System;
using System.IO;

namespace Kmrp
{
    internal static class NvidiaPresentSelfTest
    {
        private static int failures;

        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 2 && args[0] == "restore")
                {
                    NvidiaPresentOperations.Restore(args[1], Console.WriteLine);
                    return File.Exists(Path.Combine(Path.GetDirectoryName(Path.GetFullPath(args[1])),
                        "KMRP_NVIDIA.manifest")) ? 1 : 0;
                }
                if (args.Length == 2 && args[0] == "describe")
                {
                    Console.WriteLine(NvidiaPresentOperations.Describe(args[1]));
                    return 0;
                }
                if (args.Length == 2 && args[0] == "cycle")
                {
                    int result = Cycle(args[1]);
                    if (result != 0)
                        return result;
                    failures = 0;
                    result = CycleExistingProfile(args[1], false);
                    if (result != 0)
                        return result;
                    failures = 0;
                    result = CycleExistingProfile(args[1], true);
                    if (result != 0) return result;
                    result = SharedCreatedProfile(args[1]);
                    if (result != 0) return result;
                    result = SharedExistingProfile(args[1]);
                    if (result != 0) return result;
                    return ProfileNameCollision(args[1]);
                }
                Console.WriteLine("usage: describe <exe> | cycle <dir>");
                return 64;
            }
            catch (Exception ex)
            {
                Console.WriteLine("ERROR " + ex);
                return 1;
            }
        }

        private static int Cycle(string directory)
        {
            Directory.CreateDirectory(directory);
            string exe = Path.Combine(directory, "kmrp-nvapi-selftest.exe");
            File.WriteAllBytes(exe, new byte[0]);
            string manifest = Path.Combine(directory, "KMRP_NVIDIA.manifest");

            string before = NvidiaPresentOperations.Describe(exe);
            Console.WriteLine("before:   " + before);
            if (before.StartsWith("NVIDIA: unavailable", StringComparison.Ordinal))
                return 2;
            if (before.IndexOf("global Prefer layered", StringComparison.Ordinal) < 0)
            {
                Console.WriteLine("SKIP the global present method is not Prefer layered; Install would do nothing.");
                return 2;
            }
            Expect(before.IndexOf("no profile names it", StringComparison.Ordinal) >= 0,
                "the throwaway executable starts with no profile");

            NvidiaPresentEditState state = null;
            try
            {
                state = NvidiaPresentOperations.Install(exe, delegate(string m) { Console.WriteLine("report:   " + m); });
                string installed = NvidiaPresentOperations.Describe(exe);
                Console.WriteLine("install:  " + installed);
                Expect(state.Changed, "Install reports a change");
                Expect(File.Exists(manifest), "Install writes the manifest");
                Expect(installed.IndexOf("profile \"" + NvidiaPresentOperations.ProfileName + "\"", StringComparison.Ordinal) >= 0,
                    "the executable now resolves to KMRP's profile");
                Expect(installed.IndexOf("present method Prefer native from the game's own profile", StringComparison.Ordinal) >= 0,
                    "the profile holds Prefer native itself");

                NvidiaPresentEditState again = NvidiaPresentOperations.Install(exe, delegate(string m) { Console.WriteLine("report:   " + m); });
                Expect(!again.Changed, "a second Install changes nothing");
            }
            finally
            {
                NvidiaPresentOperations.Restore(exe, delegate(string m) { Console.WriteLine("report:   " + m); });
            }
            string after = NvidiaPresentOperations.Describe(exe);
            Console.WriteLine("restore:  " + after);
            Expect(!File.Exists(manifest), "Restore removes the manifest");
            Expect(after.IndexOf("no profile names it", StringComparison.Ordinal) >= 0,
                "Restore removes KMRP's profile again");
            Expect(after.EndsWith("global Prefer layered on DXGI Swapchain", StringComparison.Ordinal),
                "the global setting is untouched");

            File.Delete(exe);
            Console.WriteLine(failures == 0 ? "PASS" : "FAIL " + failures);
            return failures == 0 ? 0 : 1;
        }

        // The branch real installs take: NVIDIA ships a profile that already names
        // swkotor.exe. A throwaway profile stands in for it. With `explicitLayered`, the
        // profile itself holds Prefer layered -- a deliberate choice Install must respect.
        private const string StandInProfile = "KMRP self-test stand-in profile";

        private static int CycleExistingProfile(string directory, bool explicitLayered)
        {
            string exe = Path.Combine(directory, "kmrp-nvapi-selftest.exe");
            File.WriteAllBytes(exe, new byte[0]);
            string manifest = Path.Combine(directory, "KMRP_NVIDIA.manifest");
            Console.WriteLine(explicitLayered
                ? "-- existing profile holding Prefer layered itself"
                : "-- existing profile, present method inherited");
            WithSession(delegate(NvDrsSession drs)
            {
                IntPtr profile = drs.CreateProfile(StandInProfile);
                drs.AddApplication(profile, Path.GetFileName(exe));
                if (explicitLayered)
                    drs.SetDword(profile, 0x20D690F8, 1);
            });
            try
            {
                Console.WriteLine("before:   " + NvidiaPresentOperations.Describe(exe));
                NvidiaPresentEditState state = NvidiaPresentOperations.Install(exe,
                    delegate(string m) { Console.WriteLine("report:   " + m); });
                string installed = NvidiaPresentOperations.Describe(exe);
                Console.WriteLine("install:  " + installed);
                Expect(installed.IndexOf("profile \"" + StandInProfile + "\"", StringComparison.Ordinal) >= 0,
                    "the executable still resolves to the existing profile");
                if (explicitLayered)
                {
                    Expect(!state.Changed, "Install leaves a deliberate Prefer layered alone");
                    Expect(!File.Exists(manifest), "and writes no manifest");
                    Expect(installed.IndexOf("Prefer layered on DXGI Swapchain from the game's own profile", StringComparison.Ordinal) >= 0,
                        "the profile still holds Prefer layered");
                }
                else
                {
                    Expect(state.Changed, "Install sets the value in the existing profile");
                    Expect(installed.IndexOf("present method Prefer native from the game's own profile", StringComparison.Ordinal) >= 0,
                        "the existing profile now holds Prefer native");
                    NvidiaPresentOperations.Restore(exe, delegate(string m) { Console.WriteLine("report:   " + m); });
                    string after = NvidiaPresentOperations.Describe(exe);
                    Console.WriteLine("restore:  " + after);
                    Expect(after.IndexOf("profile \"" + StandInProfile + "\"", StringComparison.Ordinal) >= 0,
                        "Restore keeps the existing profile");
                    Expect(after.IndexOf("from the global profile", StringComparison.Ordinal) >= 0,
                        "Restore removes only KMRP's value, so it inherits again");
                    Expect(!File.Exists(manifest), "Restore removes the manifest");
                }
            }
            finally
            {
                NvidiaPresentOperations.Restore(exe, null);
                WithSession(delegate(NvDrsSession drs)
                {
                    IntPtr profile = drs.FindProfile(StandInProfile);
                    if (profile != IntPtr.Zero)
                        drs.DeleteProfile(profile);
                });
                File.Delete(exe);
            }
            string gone = NvidiaPresentOperations.Describe(exe);
            Expect(gone.IndexOf("no profile names it", StringComparison.Ordinal) >= 0, "the stand-in profile is gone");
            Console.WriteLine(failures == 0 ? "PASS" : "FAIL " + failures);
            return failures == 0 ? 0 : 1;
        }

        private static int SharedCreatedProfile(string directory)
        {
            string exe = Path.Combine(directory, "kmrp-nvapi-selftest.exe");
            File.WriteAllBytes(exe, new byte[0]);
            bool owned = false;
            try
            {
                var state = NvidiaPresentOperations.Install(exe, null);
                owned = state.Changed;
                Expect(owned, "shared test creates an owned profile");
                if (!owned) return 1;
                WithSession(delegate(NvDrsSession drs)
                {
                    var profile = drs.FindApplicationProfile(exe);
                    drs.AddApplication(profile, "kmrp-nvapi-selftest-shared.exe");
                });
                NvidiaPresentOperations.Restore(exe, null);
                WithSession(delegate(NvDrsSession drs)
                {
                    var profile = drs.FindApplicationProfile(exe);
                    Expect(profile != IntPtr.Zero, "restore preserves a profile that became shared");
                    string name; int apps, settings;
                    drs.ProfileInfo(profile, out name, out apps, out settings);
                    Expect(apps == 2, "both applications survive restore");
                    uint value; int location;
                    drs.TryGetDword(profile, 0x20D690F8, out value, out location);
                    Expect(location != NvDrsSession.LocationCurrentProfile, "only the owned setting is removed");
                });
            }
            finally
            {
                if (owned) WithSession(delegate(NvDrsSession drs)
                {
                    var profile = drs.FindProfile(NvidiaPresentOperations.ProfileName);
                    if (profile != IntPtr.Zero) drs.DeleteProfile(profile);
                });
                File.Delete(exe);
            }
            return failures == 0 ? 0 : 1;
        }

        private static int SharedExistingProfile(string directory)
        {
            string exe = Path.Combine(directory, "kmrp-nvapi-selftest.exe");
            bool owned = false;
            try
            {
                WithSession(delegate(NvDrsSession drs)
                {
                    var profile = drs.CreateProfile(StandInProfile);
                    drs.AddApplication(profile, Path.GetFileName(exe));
                    drs.AddApplication(profile, "kmrp-nvapi-selftest-shared.exe");
                });
                owned = true;
                var state = NvidiaPresentOperations.Install(exe, null);
                Expect(!state.Changed, "installation preserves an existing shared profile");
                Expect(!File.Exists(Path.Combine(directory, "KMRP_NVIDIA.manifest")), "shared profile is not claimed");
            }
            finally
            {
                if (owned) WithSession(delegate(NvDrsSession drs)
                {
                    var profile = drs.FindProfile(StandInProfile);
                    if (profile != IntPtr.Zero) drs.DeleteProfile(profile);
                });
            }
            return failures == 0 ? 0 : 1;
        }

        private static int ProfileNameCollision(string directory)
        {
            string exe = Path.Combine(directory, "kmrp-nvapi-selftest.exe");
            string manifest = Path.Combine(directory, "KMRP_NVIDIA.manifest");
            File.WriteAllBytes(exe, new byte[0]);
            bool owned = false;
            try
            {
                WithSession(delegate(NvDrsSession drs)
                {
                    if (drs.FindProfile(NvidiaPresentOperations.ProfileName) != IntPtr.Zero)
                        throw new InvalidOperationException("Refusing to overwrite an existing profile in the test.");
                    var profile = drs.CreateProfile(NvidiaPresentOperations.ProfileName);
                    drs.AddApplication(profile, "kmrp-nvapi-selftest-foreign.exe");
                    drs.SetDword(profile, 0x20D690F8, 1);
                });
                owned = true;
                var state = NvidiaPresentOperations.Install(exe, null);
                Expect(!state.Changed && !File.Exists(manifest), "same-name foreign profile is not adopted");
                WithSession(delegate(NvDrsSession drs)
                {
                    Expect(drs.FindApplicationProfile(exe) == IntPtr.Zero, "no application is added to foreign profile");
                    var profile = drs.FindProfile(NvidiaPresentOperations.ProfileName);
                    string name; int apps, settings;
                    drs.ProfileInfo(profile, out name, out apps, out settings);
                    uint value; int location;
                    drs.TryGetDword(profile, 0x20D690F8, out value, out location);
                    Expect(apps == 1 && value == 1 && location == NvDrsSession.LocationCurrentProfile,
                        "foreign application and explicit setting remain intact");
                });
            }
            finally
            {
                if (owned) WithSession(delegate(NvDrsSession drs)
                {
                    var profile = drs.FindProfile(NvidiaPresentOperations.ProfileName);
                    if (profile != IntPtr.Zero) drs.DeleteProfile(profile);
                });
                File.Delete(exe);
            }
            return failures == 0 ? 0 : 1;
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
