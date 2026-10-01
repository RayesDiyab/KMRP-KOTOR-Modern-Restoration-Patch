using System;
using System.IO;

namespace Kmrp
{
    internal static class WindowsEngineSelfTest
    {
        internal static int Main(string[] args)
        {
            Directory.CreateDirectory(args[1]);
            int count = 0;
            foreach (string line in File.ReadAllLines(args[0]))
            {
                string[] size = line.Split('x');
                ResolutionChoice resolution = ResolutionChoice.ForSize("Test", Int32.Parse(size[0]),
                    Int32.Parse(size[1]), null);
                byte[] data = WindowsEnginePatch.BuildData(resolution);
                File.WriteAllBytes(Path.Combine(args[1], resolution.Key + ".dat"), data);
                count++;
            }
            Console.WriteLine("Built runtime data for " + count + " resolutions without a game executable.");
            return 0;
        }
    }
}
