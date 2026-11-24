// CatSystem2 KIF archive patcher (ISLAND Steam JP). Port of tools/cs2.py.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace IslandKo
{
    internal sealed class Blowfish
    {
        readonly uint[] P = new uint[18];
        readonly uint[][] S = new uint[4][];

        public Blowfish(byte[] key)
        {
            Array.Copy(BlowfishTables.P, P, 18);
            for (int i = 0; i < 4; i++) { S[i] = new uint[256]; Array.Copy(BlowfishTables.S, i * 256, S[i], 0, 256); }
            int j = 0;
            for (int i = 0; i < 18; i++)
            {
                uint d = 0;
                for (int k = 0; k < 4; k++) { d = (d << 8) | key[j % key.Length]; j++; }
                P[i] ^= d;
            }
            uint l = 0, r = 0;
            for (int i = 0; i < 18; i += 2) { Enc(ref l, ref r); P[i] = l; P[i + 1] = r; }
            for (int s = 0; s < 4; s++)
                for (int i = 0; i < 256; i += 2) { Enc(ref l, ref r); S[s][i] = l; S[s][i + 1] = r; }
        }

        uint F(uint x) { return ((S[0][x >> 24] + S[1][(x >> 16) & 255]) ^ S[2][(x >> 8) & 255]) + S[3][x & 255]; }

        public void Enc(ref uint l, ref uint r)
        {
            for (int i = 0; i < 16; i++) { l ^= P[i]; r ^= F(l); uint t = l; l = r; r = t; }
            { uint t = l; l = r; r = t; }
            r ^= P[16]; l ^= P[17];
        }

        public void Dec(ref uint l, ref uint r)
        {
            for (int i = 17; i > 1; i--) { l ^= P[i]; r ^= F(l); uint t = l; l = r; r = t; }
            { uint t = l; l = r; r = t; }
            r ^= P[1]; l ^= P[0];
        }

        // CatSystem2 runs Blowfish on little-endian 32-bit halves; a tail shorter than 8 bytes is plain.
        public void EncryptLE(byte[] b, int off, int len)
        {
            int n = len / 8 * 8;
            for (int i = off; i < off + n; i += 8)
            {
                uint l = BitConverter.ToUInt32(b, i), r = BitConverter.ToUInt32(b, i + 4);
                Enc(ref l, ref r);
                PutLE(b, i, l); PutLE(b, i + 4, r);
            }
        }

        public void DecryptLE(byte[] b, int off, int len)
        {
            int n = len / 8 * 8;
            for (int i = off; i < off + n; i += 8)
            {
                uint l = BitConverter.ToUInt32(b, i), r = BitConverter.ToUInt32(b, i + 4);
                Dec(ref l, ref r);
                PutLE(b, i, l); PutLE(b, i + 4, r);
            }
        }

        static void PutLE(byte[] b, int i, uint v) { b[i] = (byte)v; b[i + 1] = (byte)(v >> 8); b[i + 2] = (byte)(v >> 16); b[i + 3] = (byte)(v >> 24); }
    }

    internal static class Cs2Key
    {
        public static uint MtFirst(uint seed)
        {
            uint[] mt = new uint[624];
            for (int i = 0; i < 624; i++)
            {
                uint upper = seed & 0xFFFF0000;
                seed = unchecked(69069 * seed + 1);
                mt[i] = upper | ((seed & 0xFFFF0000) >> 16);
                seed = unchecked(69069 * seed + 1);
            }
            uint y = (mt[0] & 0x80000000) | (mt[1] & 0x7FFFFFFF);
            y = mt[397] ^ (y >> 1) ^ ((y & 1) != 0 ? 0x9908B0DFu : 0u);
            y ^= y >> 11; y ^= (y << 7) & 0x9D2C5680; y ^= (y << 15) & 0xEFC60000; y ^= y >> 18;
            return y;
        }

        public static uint Crc(byte[] value)
        {
            uint[] table = new uint[256];
            for (uint i = 0; i < 256; i++)
            {
                uint v = i << 24;
                for (int k = 0; k < 8; k++) v = (v & 0x80000000) != 0 ? (v << 1) ^ 0x04C11DB7 : v << 1;
                table[i] = v;
            }
            uint key = 0xFFFFFFFF;
            foreach (byte b in value) key = ~table[(key >> 24) ^ b] ^ (key << 8);
            return key;
        }

        // KEY_CODE / V_CODE2 resources of ISLAND.exe -> archive name key
        public static uint MainKey(string exePath)
        {
            var res = PeResources.Read(exePath);
            byte[] key;
            byte[] kc;
            if (res.TryGetValue("KEY_CODE/KEY", out kc) && kc.Length > 0) { key = new byte[kc.Length]; for (int i = 0; i < kc.Length; i++) key[i] = (byte)(kc[i] ^ 0xCD); }
            else key = Encoding.ASCII.GetBytes("windmill");
            byte[] code;
            if (!res.TryGetValue("V_CODE2/DATA", out code)) throw new InvalidDataException("V_CODE2 resource not found in ISLAND.exe");
            code = (byte[])code.Clone();
            new Blowfish(key).DecryptLE(code, 0, code.Length);
            int z = Array.IndexOf(code, (byte)0);
            byte[] pass = new byte[z < 0 ? code.Length : z];
            Array.Copy(code, pass, pass.Length);
            return Crc(pass);
        }
    }

    internal static class PeResources
    {
        // returns "TYPE/NAME" -> data (first language); numeric ids as "#n"
        public static Dictionary<string, byte[]> Read(string path)
        {
            byte[] f = File.ReadAllBytes(path);
            int pe = BitConverter.ToInt32(f, 0x3C);
            int nsec = BitConverter.ToUInt16(f, pe + 6);
            int optSize = BitConverter.ToUInt16(f, pe + 20);
            int opt = pe + 24;
            bool pe32plus = BitConverter.ToUInt16(f, opt) == 0x20B;
            int dd = opt + (pe32plus ? 112 : 96);
            uint rsrcRva = BitConverter.ToUInt32(f, dd + 2 * 8);
            int secs = opt + optSize;
            Func<uint, int> rva2off = rva =>
            {
                for (int i = 0; i < nsec; i++)
                {
                    int s = secs + i * 40;
                    uint va = BitConverter.ToUInt32(f, s + 12), vs = BitConverter.ToUInt32(f, s + 8), raw = BitConverter.ToUInt32(f, s + 20), rs = BitConverter.ToUInt32(f, s + 16);
                    if (rva >= va && rva < va + Math.Max(vs, rs)) return (int)(rva - va + raw);
                }
                throw new InvalidDataException("RVA outside sections");
            };
            int root = rva2off(rsrcRva);
            var result = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
            Func<int, uint, string> name = (baseOff, v) =>
            {
                if ((v & 0x80000000) == 0) return "#" + v;
                int so = baseOff + (int)(v & 0x7FFFFFFF);
                int ln = BitConverter.ToUInt16(f, so);
                return Encoding.Unicode.GetString(f, so + 2, ln * 2);
            };
            Func<int, List<KeyValuePair<string, uint>>> entries = dirOff =>
            {
                var list = new List<KeyValuePair<string, uint>>();
                int n = BitConverter.ToUInt16(f, dirOff + 12) + BitConverter.ToUInt16(f, dirOff + 14);
                for (int i = 0; i < n; i++)
                {
                    uint nm = BitConverter.ToUInt32(f, dirOff + 16 + i * 8), tg = BitConverter.ToUInt32(f, dirOff + 20 + i * 8);
                    list.Add(new KeyValuePair<string, uint>(name(root, nm), tg));
                }
                return list;
            };
            foreach (var t in entries(root))
            {
                if ((t.Value & 0x80000000) == 0) continue;
                foreach (var n in entries(root + (int)(t.Value & 0x7FFFFFFF)))
                {
                    if ((n.Value & 0x80000000) == 0) continue;
                    var langs = entries(root + (int)(n.Value & 0x7FFFFFFF));
                    if (langs.Count == 0 || (langs[0].Value & 0x80000000) != 0) continue;
                    int de = root + (int)langs[0].Value;
                    uint dataRva = BitConverter.ToUInt32(f, de), size = BitConverter.ToUInt32(f, de + 4);
                    int off = rva2off(dataRva);
                    byte[] d = new byte[size];
                    Array.Copy(f, off, d, 0, size);
                    result[t.Key + "/" + n.Key] = d;
                }
            }
            return result;
        }
    }

    internal sealed class KifEntry { public int Index; public string Name; public long Offset; public uint Size; }

    // Unencrypted KIF (movie.int): [hdr][index] then per entry [its own index record][data].
    internal sealed class PlainKif
    {
        public readonly string Path;
        public readonly int Count;
        public readonly byte[] RawIndex;
        public readonly List<KifEntry> Entries = new List<KifEntry>();
        public readonly Dictionary<string, KifEntry> ByName = new Dictionary<string, KifEntry>(StringComparer.OrdinalIgnoreCase);

        public static bool IsPlain(string path)
        {
            using (var fs = File.OpenRead(path))
            {
                var b = new byte[8 + 11];
                if (fs.Read(b, 0, b.Length) != b.Length) return false;
                return b[0] == 'K' && b[1] == 'I' && b[2] == 'F' && Encoding.ASCII.GetString(b, 8, 11) != "__key__.dat";
            }
        }

        public PlainKif(string path)
        {
            Path = path;
            using (var fs = File.OpenRead(path))
            {
                var hdr = new byte[8];
                fs.Read(hdr, 0, 8);
                Count = BitConverter.ToInt32(hdr, 4);
                RawIndex = new byte[Count * 72];
                fs.Read(RawIndex, 0, RawIndex.Length);
            }
            var sjis = Encoding.GetEncoding(932);
            for (int i = 0; i < Count; i++)
            {
                int b = i * 72, n = 0;
                while (n < 64 && RawIndex[b + n] != 0) n++;
                var e = new KifEntry { Index = i, Name = sjis.GetString(RawIndex, b, n), Offset = BitConverter.ToUInt32(RawIndex, b + 64), Size = BitConverter.ToUInt32(RawIndex, b + 68) };
                Entries.Add(e);
                ByName[e.Name] = e;
            }
        }

        public byte[] Read(string name, Stream fs)
        {
            var e = ByName[name];
            var d = new byte[e.Size];
            fs.Position = e.Offset;
            int got = 0;
            while (got < d.Length) { int r = fs.Read(d, got, d.Length - got); if (r <= 0) throw new EndOfStreamException(); got += r; }
            return d;
        }

        public void Write(string outPath, IDictionary<string, byte[]> repl, Action<long, long> progress)
        {
            var index = (byte[])RawIndex.Clone();
            long cursor = 8 + (long)Count * 72;
            var lay = new List<long[]>();
            foreach (var e in Entries)
            {
                byte[] d;
                long n = repl.TryGetValue(e.Name, out d) ? (long)d.Length : (long)e.Size;
                cursor += 72;
                Buffer.BlockCopy(BitConverter.GetBytes((uint)cursor), 0, index, e.Index * 72 + 64, 4);
                Buffer.BlockCopy(BitConverter.GetBytes((uint)n), 0, index, e.Index * 72 + 68, 4);
                lay.Add(new long[] { e.Index, cursor, n });
                cursor += n;
            }
            long total = cursor, done = 0;
            var buf = new byte[1 << 20];
            using (var src = File.OpenRead(Path))
            using (var dst = new FileStream(outPath, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20))
            {
                dst.Write(Encoding.ASCII.GetBytes("KIF\0"), 0, 4);
                dst.Write(BitConverter.GetBytes(Count), 0, 4);
                dst.Write(index, 0, index.Length);
                foreach (var e in Entries)
                {
                    dst.Write(index, e.Index * 72, 72);
                    byte[] d;
                    if (repl.TryGetValue(e.Name, out d)) { dst.Write(d, 0, d.Length); done += d.Length; }
                    else
                    {
                        src.Position = e.Offset;
                        long left = e.Size;
                        while (left > 0)
                        {
                            int r = src.Read(buf, 0, (int)Math.Min(buf.Length, left));
                            if (r <= 0) throw new EndOfStreamException(Path);
                            dst.Write(buf, 0, r); left -= r; done += r;
                        }
                    }
                    if (progress != null) progress(done, total);
                }
                if (dst.Position != total) throw new InvalidDataException("size mismatch while writing " + outPath);
            }
        }
    }

    internal sealed class Kif
    {
        static readonly byte[] Alphabet = Encoding.ASCII.GetBytes("zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIHGFEDCBA");
        public readonly string Path;
        public readonly int Count;
        public readonly byte[] RawIndex;
        public readonly Blowfish Cipher;
        public readonly List<KifEntry> Entries = new List<KifEntry>();
        public readonly Dictionary<string, KifEntry> ByName = new Dictionary<string, KifEntry>(StringComparer.OrdinalIgnoreCase);
        static readonly Encoding Sjis = Encoding.GetEncoding(932);

        public Kif(string path, uint mainKey)
        {
            Path = path;
            using (var fs = File.OpenRead(path))
            {
                var hdr = new byte[8];
                ReadExact(fs, hdr, 8);
                if (hdr[0] != 'K' || hdr[1] != 'I' || hdr[2] != 'F' || hdr[3] != 0) throw new InvalidDataException(path + " is not a KIF archive");
                Count = BitConverter.ToInt32(hdr, 4);
                RawIndex = new byte[Count * 72];
                ReadExact(fs, RawIndex, RawIndex.Length);
            }
            if (Encoding.ASCII.GetString(RawIndex, 0, 11) != "__key__.dat") throw new InvalidDataException(path + ": unexpected index");
            uint seed = BitConverter.ToUInt32(RawIndex, 68);
            Cipher = new Blowfish(BitConverter.GetBytes(Cs2Key.MtFirst(seed)));
            for (int i = 1; i < Count; i++)
            {
                int b = i * 72;
                uint nk = Cs2Key.MtFirst(unchecked(mainKey + (uint)i));
                int k = (int)(((nk & 255) + ((nk >> 8) & 255) + ((nk >> 16) & 255) + (nk >> 24)) & 255);
                var nm = new List<byte>();
                for (int j = 0; j < 64; j++)
                {
                    byte c = RawIndex[b + j];
                    if (c == 0) break;
                    int a = Array.IndexOf(Alphabet, c);
                    if (a >= 0) c = Alphabet[51 - (((a - k % 52) % 52) + 52) % 52];
                    nm.Add(c);
                    k++;
                }
                var blk = new byte[8];
                Buffer.BlockCopy(BitConverter.GetBytes(unchecked(BitConverter.ToUInt32(RawIndex, b + 64) + (uint)i)), 0, blk, 0, 4);
                Buffer.BlockCopy(RawIndex, b + 68, blk, 4, 4);
                Cipher.DecryptLE(blk, 0, 8);
                var e = new KifEntry { Index = i, Name = Sjis.GetString(nm.ToArray()), Offset = BitConverter.ToUInt32(blk, 0), Size = BitConverter.ToUInt32(blk, 4) };
                Entries.Add(e);
                ByName[e.Name] = e;
            }
        }

        static void ReadExact(Stream s, byte[] buf, int n)
        {
            int got = 0;
            while (got < n) { int r = s.Read(buf, got, n - got); if (r <= 0) throw new EndOfStreamException(); got += r; }
        }

        public byte[] Read(string name, Stream fs)
        {
            var e = ByName[name];
            var d = new byte[e.Size];
            fs.Position = e.Offset;
            ReadExact(fs, d, d.Length);
            Cipher.DecryptLE(d, 0, d.Length);
            return d;
        }

        byte[] EncEntry(int i, long off, long n)
        {
            var blk = new byte[8];
            Buffer.BlockCopy(BitConverter.GetBytes((uint)off), 0, blk, 0, 4);
            Buffer.BlockCopy(BitConverter.GetBytes((uint)n), 0, blk, 4, 4);
            Cipher.EncryptLE(blk, 0, 8);
            uint x = BitConverter.ToUInt32(blk, 0);
            Buffer.BlockCopy(BitConverter.GetBytes(unchecked(x - (uint)i)), 0, blk, 0, 4);
            return blk;
        }

        // Writes [KIF hdr][index] then per entry (index order) [index record i-1][data i], the layout of the
        // original packer. Unchanged entries are copied encrypted; replacements are encrypted here.
        public void Write(string outPath, IDictionary<string, byte[]> repl, Action<long, long> progress)
        {
            foreach (var k in repl.Keys) if (!ByName.ContainsKey(k)) throw new KeyNotFoundException("entry not in " + System.IO.Path.GetFileName(Path) + ": " + k);
            var index = (byte[])RawIndex.Clone();
            var order = new List<KifEntry>(Entries);
            order.Sort((a, b) => a.Index.CompareTo(b.Index));
            long cursor = 8 + (long)Count * 72;
            var newOff = new long[Count];
            var newSize = new long[Count];
            foreach (var e in order)
            {
                byte[] d;
                long n = repl.TryGetValue(e.Name, out d) ? (long)d.Length : (long)e.Size;
                cursor += 72;
                newOff[e.Index] = cursor; newSize[e.Index] = n;
                if (cursor > uint.MaxValue) throw new InvalidDataException("archive too large");
                Buffer.BlockCopy(EncEntry(e.Index, cursor, n), 0, index, e.Index * 72 + 64, 8);
                cursor += n;
            }
            long total = cursor, done = 0;
            var buf = new byte[1 << 20];
            using (var src = File.OpenRead(Path))
            using (var dst = new FileStream(outPath, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20))
            {
                dst.Write(Encoding.ASCII.GetBytes("KIF\0"), 0, 4);
                dst.Write(BitConverter.GetBytes(Count), 0, 4);
                dst.Write(index, 0, index.Length);
                foreach (var e in order)
                {
                    dst.Write(index, (e.Index - 1) * 72, 72);
                    byte[] d;
                    if (repl.TryGetValue(e.Name, out d))
                    {
                        var c = (byte[])d.Clone();
                        Cipher.EncryptLE(c, 0, c.Length);
                        dst.Write(c, 0, c.Length);
                        done += c.Length;
                    }
                    else
                    {
                        src.Position = e.Offset;
                        long left = e.Size;
                        while (left > 0)
                        {
                            int r = src.Read(buf, 0, (int)Math.Min(buf.Length, left));
                            if (r <= 0) throw new EndOfStreamException(Path);
                            dst.Write(buf, 0, r);
                            left -= r; done += r;
                        }
                    }
                    if (progress != null) progress(done, total);
                }
                if (dst.Position != total) throw new InvalidDataException("size mismatch while writing " + outPath);
            }
        }
    }
}
