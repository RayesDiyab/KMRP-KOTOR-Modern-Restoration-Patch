using System;
using System.IO;

namespace Kmrp
{
    /// <summary>The whole patched executable for a size, which the installer's `--apply` wrote until
    /// 2026-11-01 and no install has written since 2026-09-29. For tests and the binary inventory:
    ///     kmrp-reference SOURCE.exe OUTPUT.exe [WIDTHxHEIGHT]</summary>
    internal static class ReferenceApply
    {
        internal static int Main(string[] args)
        {
            try
            {
                if (args.Length != 2 && args.Length != 3)
                    return 64;
                int width = 3440, height = 1440;
                if (args.Length == 3)
                {
                    string[] size = args[2].Split('x');
                    width = Int32.Parse(size[0]);
                    height = Int32.Parse(size[1]);
                }
                string source = Path.GetFullPath(args[0]), output = Path.GetFullPath(args[1]);
                if (String.Equals(source, output, StringComparison.OrdinalIgnoreCase))
                    throw new ArgumentException("Source and output paths must be different.");
                if (File.Exists(output))
                    throw new IOException("Output file already exists: " + output);
                ResolutionChoice resolution = ResolutionCatalog.Find(width, height);
                File.WriteAllBytes(output, WindowsEnginePatch.ApplyToExecutable(File.ReadAllBytes(source), resolution,
                    KmrpSettings.MarkerFixes));
                return 0;
            }
            catch (Exception error)
            {
                Console.Error.WriteLine(error.Message);
                return 1;
            }
        }
    }
}
