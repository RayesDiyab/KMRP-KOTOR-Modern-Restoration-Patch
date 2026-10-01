using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Text;

namespace Kmrp
{
    // A source-built recipe, not an executable delta. Offsets below are the
    // established ResolutionPatch coordinate system; the scratch array is only
    // a layout workspace and is never written as a game executable.
    internal static class WindowsEnginePatch
    {
        private const uint BlockVa = 0x0086D000;
        private const int BlockOffset = 0x003DB000, BlockSize = 0xB000;
        private const int WorkspaceSize = BlockOffset + BlockSize;
        private sealed class Site
        {
            internal uint Feature, Va;
            internal byte[] Original, Final;
        }

        internal static byte[] BuildData(ResolutionChoice resolution)
        {
            byte[] template;
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("Kmrp.engine.source"))
            {
                if (input == null)
                    throw new InvalidDataException("The source-built Windows engine patches are missing.");
                using (MemoryStream copy = new MemoryStream())
                {
                    input.CopyTo(copy);
                    template = copy.ToArray();
                }
            }
            if (template.Length < 32 || Checksum(template, template.Length - 4) !=
                BitConverter.ToUInt32(template, template.Length - 4))
                throw new InvalidDataException("The Windows engine patch template is damaged.");

            byte[] workspace = new byte[WorkspaceSize];
            bool[] covered = new bool[WorkspaceSize];
            List<Site> sites = new List<Site>();
            uint[] protections = new uint[11];
            List<uint[]> relocations = new List<uint[]>();
            using (BinaryReader reader = new BinaryReader(new MemoryStream(template, 0, template.Length - 4)))
            {
                if (Encoding.ASCII.GetString(Read(reader, 8)) != "KMRPSRC1" || reader.ReadUInt32() != 1 ||
                    reader.ReadUInt32() != BlockVa || reader.ReadUInt32() != BlockSize || reader.ReadUInt32() != 11)
                    throw new InvalidDataException("The Windows engine patch template has an unexpected layout.");
                for (int i = 0; i < protections.Length; i++)
                {
                    protections[i] = reader.ReadUInt32();
                    if (protections[i] != (i == 2 ? 0x40u : 0x20u))
                        throw new InvalidDataException("The Windows engine patch protections are damaged.");
                }
                Buffer.BlockCopy(Read(reader, BlockSize), 0, workspace, BlockOffset, BlockSize);
                for (int i = BlockOffset; i < WorkspaceSize; i++) covered[i] = true;
                int count = Count(reader, 4096);
                uint previousEnd = 0x00401000;
                for (int i = 0; i < count; i++)
                {
                    Site site = new Site { Feature = reader.ReadUInt32(), Va = reader.ReadUInt32() };
                    int size = Count(reader, 4096);
                    if ((site.Feature != 1 && site.Feature != 2) || size == 0 || site.Va < previousEnd ||
                        site.Va + (long)size > 0x007DB000)
                        throw new InvalidDataException("The Windows engine patch sites are damaged.");
                    site.Original = Read(reader, size);
                    site.Final = Read(reader, size);
                    int offset = checked((int)(site.Va - 0x00400000));
                    Buffer.BlockCopy(site.Final, 0, workspace, offset, size);
                    for (int j = 0; j < size; j++) covered[offset + j] = true;
                    previousEnd = site.Va + (uint)size;
                    sites.Add(site);
                }
                count = Count(reader, 4096);
                HashSet<uint> fields = new HashSet<uint>();
                for (int i = 0; i < count; i++)
                {
                    uint kind = reader.ReadUInt32(), field = reader.ReadUInt32();
                    if (!fields.Add(field) || kind < 1 || kind > 3 ||
                        (kind == 1 && !sites.Exists(s => field >= s.Va && field + 4L <= s.Va + s.Final.Length)) ||
                        (kind != 1 && (field < BlockVa || field + 4L > BlockVa + BlockSize)))
                        throw new InvalidDataException("The Windows engine patch relocations are damaged.");
                    relocations.Add(new[] { kind, field });
                }
                if (reader.BaseStream.Position != reader.BaseStream.Length)
                    throw new InvalidDataException("The Windows engine patch template has trailing data.");
            }

            // Ask the shared scaling code for every field it used. A future field
            // added there must also acquire an authored original-byte guard here.
            lock (typeof(ResolutionPatch))
            {
                ResolutionPatch.Touched = new List<long[]>();
                try
                {
                    ResolutionPatch.Apply(workspace, resolution);
                    foreach (long[] field in ResolutionPatch.Touched)
                        for (long i = field[0]; i < field[0] + field[1]; i++)
                            if (i < 0 || i >= covered.Length || !covered[i])
                                throw new InvalidDataException("A resolution field has no source patch guard: " +
                                    field[0].ToString("X"));
                }
                finally { ResolutionPatch.Touched = null; }
            }
            int flag = checked((int)ResolutionPatch.MapNoteFlagOffset);
            if (BitConverter.ToUInt32(workspace, flag) != 1)
                throw new InvalidDataException("The source map-note flag is damaged.");
            Array.Clear(workspace, flag, 4);
            using (MemoryStream output = new MemoryStream())
            using (BinaryWriter writer = new BinaryWriter(output))
            {
                writer.Write(Encoding.ASCII.GetBytes("KMRPKPM2"));
                writer.Write(2u);
                writer.Write(BlockVa);
                writer.Write((uint)BlockSize);
                writer.Write(11u);
                foreach (uint protection in protections) writer.Write(protection);
                writer.Write(workspace, BlockOffset, BlockSize);
                writer.Write((uint)sites.Count);
                foreach (Site site in sites)
                {
                    writer.Write(site.Feature);
                    writer.Write(site.Va);
                    writer.Write((uint)site.Original.Length);
                    writer.Write(site.Original);
                    writer.Write(workspace, checked((int)(site.Va - 0x400000)), site.Final.Length);
                }
                writer.Write(1u);       // optional map-note correction flag
                writer.Write(4u);
                writer.Write((uint)(flag - BlockOffset));
                writer.Write(4u);
                writer.Write(1u);
                writer.Write((uint)relocations.Count);
                foreach (uint[] relocation in relocations)
                {
                    writer.Write(relocation[0]);
                    writer.Write(relocation[1]);
                }
                writer.Flush();
                byte[] body = output.ToArray();
                writer.Write(Checksum(body, body.Length));
                writer.Flush();
                return output.ToArray();
            }
        }

        // Offline regression/reference output only. Normal installs use BuildData
        // and never write this image to the player's executable. A reference may
        // be generated from a hash-verified editable CD/GOG file if one is available;
        // that file is no longer an installer build input.
        internal static byte[] ApplyToExecutable(byte[] source, ResolutionChoice resolution, bool mapNotes)
        {
            byte[] normalized;
            if (!PeCompatibility.TryNormalizeSupportedSource(source, out normalized))
                throw new InvalidDataException("Reference output requires the supported editable 1.03 executable.");
            byte[] image = new byte[WorkspaceSize];
            Buffer.BlockCopy(normalized, 0, image, 0, normalized.Length);
            byte[] data = BuildData(resolution);
            using (BinaryReader reader = new BinaryReader(new MemoryStream(data)))
            {
                Read(reader, 24); // signature, version, block VA/size, page count
                Read(reader, 44); // protections
                Buffer.BlockCopy(Read(reader, BlockSize), 0, image, BlockOffset, BlockSize);
                int count = Count(reader, 4096);
                for (int i = 0; i < count; i++)
                {
                    reader.ReadUInt32(); // all features in reference output
                    uint va = reader.ReadUInt32();
                    int size = Count(reader, 4096);
                    byte[] original = Read(reader, size), final = Read(reader, size);
                    int offset = checked((int)(va - 0x400000));
                    for (int j = 0; j < size; j++)
                        if (image[offset + j] != original[j])
                            throw new InvalidDataException("Reference patch guard failed at " + va.ToString("X8"));
                    Buffer.BlockCopy(final, 0, image, offset, size);
                }
            }
            if (mapNotes) ResolutionPatch.WriteInt32(image, ResolutionPatch.MapNoteFlagOffset, 1);
            int pe = BitConverter.ToInt32(image, 0x3C);
            int optional = pe + 24;
            int table = optional + BitConverter.ToUInt16(image, pe + 20);
            int sections = BitConverter.ToUInt16(image, pe + 6);
            if (sections != 4 || BitConverter.ToUInt32(image, optional + 56) != 0x46D000 ||
                table + 15 * 40 > BitConverter.ToUInt32(image, optional + 60))
                throw new InvalidDataException("Reference executable has an unexpected PE layout.");
            byte[] sectionCount = BitConverter.GetBytes((ushort)15);
            Buffer.BlockCopy(sectionCount, 0, image, pe + 6, 2);
            byte[] characteristics = BitConverter.GetBytes((ushort)(BitConverter.ToUInt16(image, pe + 22) | 0x20));
            Buffer.BlockCopy(characteristics, 0, image, pe + 22, 2);
            ResolutionPatch.WriteInt32(image, optional + 4, checked(BitConverter.ToInt32(image, optional + 4) + BlockSize));
            ResolutionPatch.WriteInt32(image, optional + 56, 0x478000);
            ResolutionPatch.WriteInt32(image, optional + 64, 0);
            string[] names = { ".kui", ".klb", ".kfs", ".kwl", ".ksc", ".kgs", ".ktn", ".kmz", ".kfg", ".kmn", ".kmv" };
            int[] used = { 445, 110, 482, 17, 45, 74, 42, 181, 155, 4094, 81 };
            for (int i = 0; i < names.Length; i++)
            {
                int at = table + (sections + i) * 40;
                Array.Clear(image, at, 40);
                byte[] name = Encoding.ASCII.GetBytes(names[i]);
                Buffer.BlockCopy(name, 0, image, at, name.Length);
                ResolutionPatch.WriteInt32(image, at + 8, used[i]);
                ResolutionPatch.WriteInt32(image, at + 12, checked((int)(BlockVa - 0x400000)) + i * 0x1000);
                ResolutionPatch.WriteInt32(image, at + 16, 0x1000);
                ResolutionPatch.WriteInt32(image, at + 20, BlockOffset + i * 0x1000);
                ResolutionPatch.WriteInt32(image, at + 36, unchecked((int)(i == 2 ? 0xE0000020u : 0x60000020u)));
            }
            return image;
        }

        private static byte[] Read(BinaryReader reader, int size)
        {
            byte[] data = reader.ReadBytes(size);
            if (data.Length != size) throw new InvalidDataException("The Windows engine patch template is truncated.");
            return data;
        }

        private static int Count(BinaryReader reader, int maximum)
        {
            uint count = reader.ReadUInt32();
            if (count > maximum) throw new InvalidDataException("The Windows engine patch template has an invalid count.");
            return (int)count;
        }

        private static uint Checksum(byte[] data, int size)
        {
            uint hash = 2166136261u;
            for (int i = 0; i < size; i++) hash = unchecked((hash ^ data[i]) * 16777619u);
            return hash;
        }
    }
}
