// Self-test for the installer's update check, compiled together with the patcher source
// by Test-UpdateCheck.ps1 so it exercises exactly the code the patcher ships.
//
//   (no arguments)       the tag parser, the version comparison, and the remembered
//                        "Don't remind me again for <version>" round trip through settings.json
//   render <png> <scale> draws the update dialog, as the player would see it, to a PNG
//   live                 asks GitHub once, as the patcher does, and prints the answer;
//                        informational, since it depends on the network
//
// Exit codes: 0 pass, 1 fail.
using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Text;
using System.Windows.Forms;

namespace Kmrp
{
    internal static class UpdateCheckSelfTest
    {
        private static int failures;

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                if (args.Length == 1 && args[0] == "live")
                {
                    string latest = UpdateCheck.LatestVersion();
                    Console.WriteLine(latest == null
                        ? "no answer (offline, rate limited, or the tag is not a version)"
                        : "latest release: " + latest + (UpdateCheck.IsNewer(latest, GoldPatch.PatchVersion)
                            ? " -- newer than " + GoldPatch.PatchVersion + ", the patcher would offer it"
                            : " -- not newer than " + GoldPatch.PatchVersion + ", the patcher stays quiet"));
                    return 0;
                }
                if (args.Length == 3 && args[0] == "render")
                    return Render(args[1], Single.Parse(args[2], System.Globalization.CultureInfo.InvariantCulture));

                Tags();
                Comparison();
                Remembered();
                Console.WriteLine(failures == 0 ? "PASS: update check" : "FAIL: " + failures + " check(s)");
                return failures == 0 ? 0 : 1;
            }
            catch (Exception ex)
            {
                Console.WriteLine("FAIL: " + ex);
                return 1;
            }
        }

        private static void Check(bool ok, string what)
        {
            if (!ok)
            {
                failures++;
                Console.WriteLine("  FAIL " + what);
            }
        }

        private static void Tags()
        {
            // The real answer's shape, trimmed: GitHub puts tag_name after url and id.
            Check(UpdateCheck.VersionFromReleaseJson(
                "{\"url\":\"https://api.github.com/x\",\"id\":1,\"tag_name\":\"v1.0.0\",\"name\":\"KMRP 1.0.0\"}") == "1.0.0",
                "v1.0.0 reads as 1.0.0");
            Check(UpdateCheck.VersionFromReleaseJson("{\"tag_name\" : \"1.6.0\"}") == "1.6.0",
                "a tag without the v, spaced");
            Check(UpdateCheck.VersionFromReleaseJson("{\"tag_name\":\"v1.6\"}") == "1.6",
                "a two-part tag");
            Check(UpdateCheck.VersionFromReleaseJson("{\"tag_name\":\"v1.6.0-beta\"}") == null,
                "a suffixed tag is not a release version");
            Check(UpdateCheck.VersionFromReleaseJson("{\"message\":\"API rate limit exceeded\"}") == null,
                "a rate-limit answer has no version");
            Check(UpdateCheck.VersionFromReleaseJson("") == null && UpdateCheck.VersionFromReleaseJson(null) == null,
                "nothing has no version");
        }

        private static void Comparison()
        {
            string current = GoldPatch.PatchVersion;
            Check(current == "1.5.0", "this build is 1.5.0 (update these cases when it changes)");
            Check(!UpdateCheck.IsNewer("1.0.0", current), "the 1.0.0 release is not offered to 1.5.0");
            Check(!UpdateCheck.IsNewer("1.5.0", current), "the same version is not offered");
            Check(UpdateCheck.IsNewer("1.5.1", current), "1.5.1 is offered");
            Check(UpdateCheck.IsNewer("1.6", current), "1.6 is offered");
            Check(!UpdateCheck.IsNewer("1.6", "1.6.0"), "1.6 and 1.6.0 are the same");
            Check(UpdateCheck.IsNewer("1.10.0", "1.9.0"), "numbers, not text: 1.10 is after 1.9");
            // Why the first release's tag was moved: as a version, its internal number
            // is later than every public one.
            Check(UpdateCheck.IsNewer("2.10.0", current), "the old v2.10.0 tag would have been offered");
            Check(!UpdateCheck.IsNewer(null, current) && !UpdateCheck.IsNewer("abc", current) &&
                  !UpdateCheck.IsNewer("1.6.0-beta", current) && !UpdateCheck.IsNewer("1.6.0", ""),
                "anything that is not a version is never newer");
        }

        /// <summary>Through the real settings file, which is put back byte for byte.</summary>
        private static void Remembered()
        {
            string path = KmrpSettings.SettingsPath;
            bool existed = File.Exists(path);
            byte[] original = existed ? File.ReadAllBytes(path) : null;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.WriteAllText(path,
                    "{\r\n  \"driverCompatibility\": true,\r\n  \"markerFixes\": true,\r\n" +
                    "  \"controllerSupport\": false,\r\n  \"skippedUpdate\": \"1.6.0\"\r\n}\r\n",
                    new UTF8Encoding(false));
                Check(KmrpSettings.SkippedUpdate == "1.6.0", "a turned-off version is read back");
                Check(!KmrpSettings.ControllerSupport, "the other settings are read beside it");

                KmrpSettings.SkippedUpdate = "1.7.0";
                string written = File.ReadAllText(path);
                Check(written.Contains("\"skippedUpdate\": \"1.7.0\""), "a new turned-off version is written");
                Check(written.Contains("\"controllerSupport\": false"), "writing it keeps the other settings");

                KmrpSettings.SkippedUpdate = "";
                written = File.ReadAllText(path);
                Check(!written.Contains("skippedUpdate") && written.TrimEnd().EndsWith("\"controllerSupport\": false\r\n}"),
                    "clearing it writes the three-key file of before");
            }
            finally
            {
                if (existed)
                    File.WriteAllBytes(path, original);
                else if (File.Exists(path))
                    File.Delete(path);
            }
        }

        private static int Render(string png, float scale)
        {
            Application.EnableVisualStyles();
            using (UpdateDialog dialog = new UpdateDialog("1.6.0", GoldPatch.PatchVersion, scale))
            {
                // Shown, off screen: an unshown form draws its own background but none
                // of its children.
                dialog.StartPosition = FormStartPosition.Manual;
                dialog.Location = new Point(-20000, -20000);
                dialog.Show();
                Application.DoEvents();
                using (Bitmap bitmap = new Bitmap(dialog.Width, dialog.Height))
                {
                    dialog.DrawToBitmap(bitmap, new Rectangle(0, 0, bitmap.Width, bitmap.Height));
                    bitmap.Save(png, ImageFormat.Png);
                }
                Console.WriteLine("rendered " + dialog.ClientSize.Width + "x" + dialog.ClientSize.Height +
                    " at scale " + scale + " to " + png);
            }
            return 0;
        }
    }
}
