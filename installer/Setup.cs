// ISLAND Korean patch - installer / uninstaller / language switch for both PC builds:
//   Japanese build (engine 2.6.1.68, Steam's Japanese depot)  - internal edition name "steam"
//   English build  (engine 2.6.1.80, language.txt: GOG, and Steam with the game language set to
//                   English - the same exe wrapped in SteamStub)  - internal edition name "gog"
// The build picks the data branch; SteamStub (.bind) only decides launching through Steam.
// Originals are never modified: the patch adds version.dll, island-ko.ini and the ko\ folder;
// Korean archives are built in ko\ from the player's own original archives + our entries.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: System.Reflection.AssemblyTitle("ISLAND Korean patch setup (Japanese / English build)")]
[assembly: System.Reflection.AssemblyProduct("island-steam-ko")]
[assembly: System.Reflection.AssemblyVersion("1.3.0.0")]

namespace IslandKo
{
    internal sealed class Manifest
    {
        public readonly Dictionary<string, string> Values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public readonly List<string[]> Rows = new List<string[]>();
        public string Version { get { return Get("version", "?"); } }
        public string Get(string k, string d) { string v; return Values.TryGetValue(k, out v) ? v : d; }

        public static Manifest Load(string path)
        {
            var m = new Manifest();
            foreach (var raw in File.ReadAllLines(path, Encoding.UTF8))
            {
                var line = raw.TrimEnd('\r');
                if (line.Length == 0 || line.StartsWith("#")) continue;
                var p = line.Split('\t');
                if (p[0] == "set" && p.Length >= 3) m.Values[p[1]] = p[2];
                else m.Rows.Add(p);
            }
            return m;
        }

        public IEnumerable<string[]> Of(string kind) { return Rows.Where(r => r[0] == kind); }
        // rows of one kind for an edition: column 1 is the edition ("steam", "gog") or "all"
        public IEnumerable<string[]> Of(string kind, string edition) { return Of(kind).Where(r => r.Length > 1 && (r[1] == edition || r[1] == "all")); }
    }

    internal sealed class Patcher
    {
        public const int AppId = 857450;
        public readonly string PatchDir, PayloadDir;
        public readonly Manifest M;
        public string GameDir;
        public Action<string> Log = s => Console.WriteLine(s);
        public Action<int> Progress = p => { };
        public readonly List<string> Warnings = new List<string>();

        public Patcher(string patchDir)
        {
            PatchDir = patchDir;
            PayloadDir = Path.Combine(patchDir, "payload");
            M = Manifest.Load(Path.Combine(PayloadDir, "manifest.txt"));
        }

        public static string Sha256(string path)
        {
            using (var s = File.OpenRead(path))
            using (var h = SHA256.Create())
                return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "").ToLowerInvariant();
        }

        public static string Sha1(string path)
        {
            using (var s = File.OpenRead(path))
            using (var h = SHA1.Create())
                return BitConverter.ToString(h.ComputeHash(s)).Replace("-", "").ToLowerInvariant();
        }

        // a manifest hash cell: a SHA-256 in hex, or "sha1:<hex>" (Steam's depot manifests give SHA-1 only)
        readonly Dictionary<string, string> sha1Cache = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        bool HashIs(string cell, string path, string sha256)
        {
            if (cell.StartsWith("sha1:", StringComparison.OrdinalIgnoreCase))
            {
                string h1;
                if (!sha1Cache.TryGetValue(path, out h1)) sha1Cache[path] = h1 = Sha1(path);
                return string.Equals(cell.Substring(5), h1, StringComparison.OrdinalIgnoreCase);
            }
            return string.Equals(cell, sha256, StringComparison.OrdinalIgnoreCase);
        }

        // ---- game folder detection: Steam libraries, then GOG Galaxy's registry ----
        public static string FindGame()
        {
            var cands = new List<string>();
            try
            {
                var sp = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Valve\Steam", "SteamPath", null) as string;
                if (sp != null)
                {
                    var libs = new List<string> { sp };
                    var lf = Path.Combine(sp, "steamapps", "libraryfolders.vdf");
                    if (File.Exists(lf))
                        foreach (Match m in Regex.Matches(File.ReadAllText(lf), "\"path\"\\s+\"([^\"]+)\""))
                            libs.Add(m.Groups[1].Value.Replace("\\\\", "\\"));
                    foreach (var lib in libs)
                    {
                        var acf = Path.Combine(lib, "steamapps", "appmanifest_" + AppId + ".acf");
                        if (!File.Exists(acf)) continue;
                        var m = Regex.Match(File.ReadAllText(acf), "\"installdir\"\\s+\"([^\"]+)\"");
                        if (m.Success) cands.Add(Path.Combine(lib, "steamapps", "common", m.Groups[1].Value));
                    }
                }
            }
            catch { }
            foreach (var root in new[] { @"SOFTWARE\WOW6432Node\GOG.com\Games", @"SOFTWARE\GOG.com\Games" })
            {
                try
                {
                    using (var k = Registry.LocalMachine.OpenSubKey(root))
                    {
                        if (k == null) continue;
                        foreach (var id in k.GetSubKeyNames())
                            using (var g = k.OpenSubKey(id))
                            {
                                var name = g == null ? null : g.GetValue("gameName") as string;
                                var path = g == null ? null : g.GetValue("path") as string;
                                if (name != null && path != null && name.Trim().Equals("ISLAND", StringComparison.OrdinalIgnoreCase)) cands.Add(path);
                            }
                    }
                }
                catch { }
            }
            foreach (var c in cands) if (File.Exists(Path.Combine(c, "ISLAND.exe"))) return Path.GetFullPath(c);
            return null;
        }

        public static string SteamLaunchOptions()
        {
            var found = new List<string>();
            try
            {
                var sp = Registry.GetValue(@"HKEY_CURRENT_USER\Software\Valve\Steam", "SteamPath", null) as string;
                if (sp == null) return null;
                var ud = Path.Combine(sp, "userdata");
                if (!Directory.Exists(ud)) return null;
                foreach (var d in Directory.GetDirectories(ud))
                {
                    var lc = Path.Combine(d, "config", "localconfig.vdf");
                    if (!File.Exists(lc)) continue;
                    var t = File.ReadAllText(lc, Encoding.UTF8);
                    foreach (Match m in Regex.Matches(t, "\\n(\\t+)\"" + AppId + "\"\\n\\1\\{\\n"))
                    {
                        int end = t.IndexOf("\n" + m.Groups[1].Value + "}", m.Index + m.Length, StringComparison.Ordinal);
                        if (end < 0) continue;
                        var block = t.Substring(m.Index + m.Length, end - m.Index - m.Length);
                        var lm = Regex.Match(block, "\"LaunchOptions\"\\t\\t\"((?:[^\"\\\\]|\\\\.)*)\"");
                        if (lm.Success && lm.Groups[1].Value.Trim().Length > 0)
                            found.Add(Regex.Replace(lm.Groups[1].Value, "\\\\(.)", "$1"));
                    }
                }
            }
            catch { }
            return found.Count > 0 ? string.Join(" | ", found.Distinct()) : null;
        }

        static bool HasSection(string exe, string name)
        {
            try
            {
                byte[] f = new byte[65536];   // the section table sits in the PE headers
                using (var s = File.OpenRead(exe)) Array.Resize(ref f, s.Read(f, 0, f.Length));
                int pe = BitConverter.ToInt32(f, 0x3C);
                int nsec = BitConverter.ToUInt16(f, pe + 6);
                int secs = pe + 24 + BitConverter.ToUInt16(f, pe + 20);
                for (int i = 0; i < nsec; i++)
                    if (Encoding.ASCII.GetString(f, secs + i * 40, 8).TrimEnd('\0') == name) return true;
            }
            catch { }
            return false;
        }

        bool GameRunning()
        {
            foreach (var p in Process.GetProcessesByName("ISLAND"))
            {
                try
                {
                    var f = p.MainModule.FileName;
                    if (f != null && Path.GetFullPath(f).StartsWith(Path.GetFullPath(GameDir), StringComparison.OrdinalIgnoreCase)) return true;
                }
                catch { return true; }
            }
            return false;
        }

        string G(string rel) { return Path.Combine(GameDir, rel); }
        string KoDir { get { return G("ko"); } }
        public bool Installed { get { return File.Exists(Path.Combine(KoDir, "install.txt")); } }
        // the build ko\ was made for (install.txt "edition ..."); Steam swaps the game files when its
        // game language changes, and version.dll then stays in the original language until reinstalled
        public string InstalledEdition
        {
            get
            {
                try
                {
                    var m = Regex.Match(File.ReadAllText(Path.Combine(KoDir, "install.txt")), "(?m)^edition (\\w+)");
                    return m.Success ? m.Groups[1].Value : null;
                }
                catch { return null; }
            }
        }

        // ---- edition = the build: exe hash known to the manifest, else the build's own marks ----
        //  "gog"   English build: language.txt in the folder, or exe version 2.6.1.80
        //  "steam" Japanese build: everything else (Steam's Japanese depot, 2.6.1.68)
        // SteamStub (.bind) is in both Steam depots, so it never picks the data branch (IsSteam).
        string edition, editionFor;
        public string Edition
        {
            get
            {
                if (GameDir == null || !File.Exists(G("ISLAND.exe"))) return null;
                if (edition != null && editionFor == GameDir) return edition;
                string e = null;
                var exe = G("ISLAND.exe");
                var h = Sha256(exe);
                foreach (var r in M.Of("edition"))
                    if (HashIs(r[2], exe, h) || r.Skip(4).Any(c => HashIs(c, exe, h))) e = r[1];
                if (e == null) e = File.Exists(G("language.txt")) || ExeVersion() == "2.6.1.80" ? "gog" : "steam";
                edition = e; editionFor = GameDir;
                return e;
            }
        }
        // the exe carries SteamStub: start it through Steam, and Steam's launch options matter
        public bool IsSteam { get { return GameDir != null && HasSection(G("ISLAND.exe"), ".bind"); } }
        public string ExeVersion()
        {
            try
            {
                var v = FileVersionInfo.GetVersionInfo(G("ISLAND.exe"));
                return v.FileMajorPart + "." + v.FileMinorPart + "." + v.FileBuildPart + "." + v.FilePrivatePart;
            }
            catch { return ""; }
        }
        public string EditionLabel(string e)
        {
            if (e == null) return "알 수 없는 판";
            var r = M.Of("edition").FirstOrDefault(x => x[1] == e);
            return (r != null && r.Length > 3 ? r[3] : e) + (IsSteam ? " · 스팀" : "");
        }
        public string OriginalLanguage { get { return Edition == "gog" ? "en" : "ja"; } }
        public string OriginalLabel { get { return Edition == "gog" ? "English(원래 게임)" : "日本語(원래 게임)"; } }

        public string Language()
        {
            var ini = G("island-ko.ini");
            if (!File.Exists(ini)) return null;
            var m = Regex.Match(File.ReadAllText(ini), "(?im)^\\s*language\\s*=\\s*(\\w+)");
            return m.Success ? m.Groups[1].Value.ToLowerInvariant() : "ko";
        }

        public void SetLanguage(string lang)
        {
            if (lang != "ko") lang = OriginalLanguage;
            File.WriteAllText(G("island-ko.ini"), "[ISLAND-KO]\r\n; ko = 한국어, ja / en = 원래 게임(일본어판 / 영어판)\r\nlanguage=" + lang + "\r\n", new UTF8Encoding(false));
            Log(lang == "ko" ? "언어: 한국어. 다음 실행부터 적용됩니다." : "언어: " + OriginalLabel + ". 다음 실행부터 적용됩니다.");
        }

        public void CheckOriginals()
        {
            var ed = Edition;
            foreach (var r in M.Of("orig", ed))
            {
                var p = G(r[2]);
                if (!File.Exists(p)) { Warnings.Add("원본 파일이 없습니다: " + r[2]); Log("경고: 원본 파일이 없습니다 - " + r[2]); continue; }
                Log("원본 확인: " + r[2]);
                var h = Sha256(p);
                // column 3 is the SHA-256; further columns are other known copies ("sha1:..." = Steam English exe)
                if (!r.Skip(3).Any(c => HashIs(c, p, h)))
                {
                    Warnings.Add(r[2] + " 이(가) 이 패치를 만든 판과 다릅니다(업데이트 등). 설치는 계속하지만 일부가 맞지 않을 수 있습니다.");
                    Log("경고: " + r[2] + " 해시가 다릅니다 (" + h.Substring(0, 12) + ")");
                }
            }
        }

        public void Install()
        {
            if (!File.Exists(G("ISLAND.exe"))) throw new InvalidOperationException("게임 폴더에 ISLAND.exe 가 없습니다: " + GameDir);
            if (GameRunning()) throw new InvalidOperationException("ISLAND 가 실행 중입니다. 게임을 끄고 다시 해 주세요.");
            var ed = Edition;
            if (ed == null || !M.Of("archive", ed).Any()) throw new InvalidOperationException("이 패치가 아는 ISLAND 판(일본어판·영어판)이 아닙니다.");
            var lost = M.Of("archive", ed).Select(a => a[2]).Where(n => !File.Exists(G(n))).ToList();
            if (lost.Count > 0) throw new InvalidOperationException("게임 폴더에 원본 파일이 없습니다: " + string.Join(", ", lost));
            Warnings.Clear();
            Log("게임 폴더: " + GameDir);
            Log("판: " + EditionLabel(ed));
            CheckOriginals();
            if (IsSteam)
            {
                var lo = SteamLaunchOptions();
                if (lo != null) Warnings.Add("스팀 실행 옵션이 설정되어 있습니다: " + lo + "\r\n  이 옵션이 다른 폴더의 게임을 띄우면 패치가 보이지 않습니다. 스팀 → 라이브러리 → ISLAND → 속성 → 일반 → 실행 옵션을 비워 주세요.");
            }
            // a previous install of the other edition's files must not linger in ko\
            if (Directory.Exists(KoDir)) Directory.Delete(KoDir, true);
            Directory.CreateDirectory(KoDir);
            // existing version.dll that is not ours -> keep a copy
            var vd = G("version.dll");
            var ourDll = M.Get("dll_sha256", "");
            if (File.Exists(vd))
            {
                var h = Sha256(vd);
                var known = M.Of("known_dll").Select(x => x[1]).Concat(new[] { ourDll });
                if (!known.Contains(h, StringComparer.OrdinalIgnoreCase))
                {
                    Directory.CreateDirectory(G("ko-backup"));
                    var bk = Path.Combine(G("ko-backup"), "version.dll");
                    if (!File.Exists(bk)) File.Copy(vd, bk);
                    Warnings.Add("게임 폴더에 다른 version.dll 이 있어 ko-backup 에 옮겨 두었습니다(되돌리기 때 복원).");
                }
            }
            // static files
            var files = M.Of("file", ed).ToList();
            int i = 0;
            foreach (var r in files)
            {
                var src = Path.Combine(PayloadDir, r[2]);
                var dst = G(r[3]);
                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                File.Copy(src, dst, true);
                Progress(++i * 10 / Math.Max(1, files.Count));
            }
            Log("파일 " + files.Count + "개를 넣었습니다.");
            // archives
            uint key = Cs2Key.MainKey(G("ISLAND.exe"));
            var archives = M.Of("archive", ed).ToList();
            long sizeAll = archives.Sum(a => new FileInfo(G(a[2])).Length);
            long doneAll = 0;
            foreach (var a in archives)
            {
                string name = a[2], dirRel = a[3], expect = a.Length > 4 ? a[4] : "";
                bool plain = PlainKif.IsPlain(G(name));
                Kif kif = plain ? null : new Kif(G(name), key);
                PlainKif pk = plain ? new PlainKif(G(name)) : null;
                var repl = new Dictionary<string, byte[]>(StringComparer.OrdinalIgnoreCase);
                foreach (var d in dirRel.Split(';'))
                    foreach (var f in Directory.GetFiles(Path.Combine(PayloadDir, d))) repl[Path.GetFileName(f)] = File.ReadAllBytes(f);
                var missing = repl.Keys.Where(k => !(plain ? pk.ByName.ContainsKey(k) : kif.ByName.ContainsKey(k))).ToList();
                if (missing.Count > 0) { Warnings.Add(name + " 에 없는 항목 " + missing.Count + "개는 건너뜁니다."); foreach (var k in missing) repl.Remove(k); }
                Log(name + " → ko\\" + name + " (" + repl.Count + "개 항목 한국어)");
                var outp = Path.Combine(KoDir, name);
                var tmp = outp + ".tmp";
                long baseDone = doneAll, mySize = new FileInfo(G(name)).Length;
                Action<long, long> prog = (d, t) => Progress(10 + (int)(85 * (baseDone + d * mySize / Math.Max(1, t)) / Math.Max(1, sizeAll)));
                if (plain) pk.Write(tmp, repl, prog); else kif.Write(tmp, repl, prog);
                // read back the replaced entries
                using (var fs = File.OpenRead(tmp))
                {
                    if (plain)
                    {
                        var chk = new PlainKif(tmp);
                        foreach (var kv in repl)
                            if (!chk.Read(kv.Key, fs).SequenceEqual(kv.Value)) throw new InvalidDataException("검증 실패: " + name + " / " + kv.Key);
                    }
                    else
                    {
                        var chk = new Kif(tmp, key);
                        foreach (var kv in repl)
                            if (!chk.Read(kv.Key, fs).SequenceEqual(kv.Value)) throw new InvalidDataException("검증 실패: " + name + " / " + kv.Key);
                    }
                }
                if (File.Exists(outp)) File.Delete(outp);
                File.Move(tmp, outp);
                doneAll += mySize;
                if (expect.Length > 0)
                {
                    var h = Sha256(outp);
                    if (!string.Equals(h, expect, StringComparison.OrdinalIgnoreCase)) Log("참고: ko\\" + name + " 는 예상 해시와 다릅니다(원본 판이 달라서). " + h.Substring(0, 12));
                    else Log("ko\\" + name + " 해시 일치");
                }
            }
            File.Copy(Path.Combine(PayloadDir, "version.dll"), vd, true);
            var cur = Language();
            if (cur == null) SetLanguage("ko");
            else if (cur != "ko" && cur != OriginalLanguage) SetLanguage(OriginalLanguage);   // e.g. "ja" left on a GOG folder
            var rec = new StringBuilder();
            rec.AppendLine("ISLAND Korean patch " + M.Version);
            rec.AppendLine("edition " + ed);
            rec.AppendLine("installed " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            foreach (var w in Warnings) rec.AppendLine("warning " + w.Replace("\r\n", " "));
            File.WriteAllText(Path.Combine(KoDir, "install.txt"), rec.ToString(), new UTF8Encoding(false));
            Progress(100);
            Log("설치를 마쳤습니다. 원본 파일은 바꾸지 않았습니다.");
        }

        public void Uninstall()
        {
            if (GameRunning()) throw new InvalidOperationException("ISLAND 가 실행 중입니다. 게임을 끄고 다시 해 주세요.");
            var vd = G("version.dll");
            if (File.Exists(vd))
            {
                var h = Sha256(vd);
                var ours = M.Of("known_dll").Select(x => x[1]).Concat(new[] { M.Get("dll_sha256", "") });
                if (ours.Contains(h, StringComparer.OrdinalIgnoreCase)) { File.Delete(vd); Log("version.dll 을 지웠습니다."); }
                else Log("version.dll 이 이 패치 것이 아니어서 그대로 둡니다.");
            }
            var bk = Path.Combine(G("ko-backup"), "version.dll");
            if (File.Exists(bk) && !File.Exists(vd)) { File.Move(bk, vd); Log("원래 있던 version.dll 을 되돌렸습니다."); }
            if (Directory.Exists(G("ko-backup")) && !Directory.EnumerateFileSystemEntries(G("ko-backup")).Any()) Directory.Delete(G("ko-backup"));
            foreach (var f in new[] { "island-ko.ini", "island-ko.log" }) if (File.Exists(G(f))) File.Delete(G(f));
            if (Directory.Exists(KoDir)) { Directory.Delete(KoDir, true); Log("ko 폴더를 지웠습니다."); }
            Warnings.Clear();
            CheckOriginals();
            Log(Warnings.Count == 0 ? "되돌리기를 마쳤습니다. 원본 파일이 모두 그대로입니다." : "되돌리기를 마쳤습니다(위 경고 참고).");
        }

        public void Play()
        {
            if (IsSteam) Process.Start("steam://rungameid/" + AppId);
            else Process.Start(new ProcessStartInfo(G("ISLAND.exe")) { WorkingDirectory = GameDir, UseShellExecute = true });
        }
    }

    internal sealed class MainForm : Form
    {
        readonly Patcher P;
        readonly TextBox Folder = new TextBox(), LogBox = new TextBox();
        readonly Label State = new Label();
        readonly ProgressBar Bar = new ProgressBar();
        readonly Button BInstall = new Button(), BRemove = new Button(), BKo = new Button(), BOrig = new Button(), BBrowse = new Button(), BPlay = new Button();

        public MainForm(Patcher p)
        {
            P = p;
            Text = "ISLAND 한국어 패치 (일본어판·영어판) " + p.M.Version;
            Font = new Font("Malgun Gothic", 9.5f);
            ClientSize = new Size(640, 470);
            FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
            var l1 = new Label { Text = "게임 폴더", Location = new Point(14, 16), AutoSize = true };
            Folder.SetBounds(90, 12, 440, 26); Folder.Text = p.GameDir ?? "";
            BBrowse.SetBounds(538, 11, 88, 28); BBrowse.Text = "찾아보기";
            State.SetBounds(14, 48, 612, 24);
            BInstall.SetBounds(14, 80, 150, 36); BInstall.Text = "설치 / 다시 설치";
            BRemove.SetBounds(172, 80, 150, 36); BRemove.Text = "되돌리기(지우기)";
            BKo.SetBounds(330, 80, 95, 36); BKo.Text = "한국어로";
            BOrig.SetBounds(431, 80, 95, 36); BOrig.Text = "원래 언어로";
            BPlay.SetBounds(532, 80, 94, 36); BPlay.Text = "게임 실행";
            Bar.SetBounds(14, 124, 612, 16);
            LogBox.SetBounds(14, 148, 612, 308); LogBox.Multiline = true; LogBox.ScrollBars = ScrollBars.Vertical; LogBox.ReadOnly = true;
            Controls.AddRange(new Control[] { l1, Folder, BBrowse, State, BInstall, BRemove, BKo, BOrig, BPlay, Bar, LogBox });
            P.Log = s => { LogBox.AppendText(s + "\r\n"); Application.DoEvents(); };
            P.Progress = v => { Bar.Value = Math.Max(0, Math.Min(100, v)); Application.DoEvents(); };
            BBrowse.Click += (s, e) => { using (var d = new FolderBrowserDialog { Description = "ISLAND.exe 가 있는 폴더를 고르세요" }) if (d.ShowDialog(this) == DialogResult.OK) { Folder.Text = d.SelectedPath; Refresh2(); } };
            Folder.Leave += (s, e) => Refresh2();
            BInstall.Click += (s, e) => Run(() => P.Install(), true);
            BRemove.Click += (s, e) => { if (MessageBox.Show(this, "한국어 패치를 지우고 원래 게임으로 돌아갑니다. 세이브는 그대로입니다.", Text, MessageBoxButtons.OKCancel) == DialogResult.OK) Run(() => P.Uninstall(), false); };
            BKo.Click += (s, e) => Run(() => P.SetLanguage("ko"), false);
            BOrig.Click += (s, e) => Run(() => P.SetLanguage("original"), false);
            BPlay.Click += (s, e) => { try { P.Play(); } catch (Exception ex) { P.Log(ex.Message); } };
            Refresh2();
        }

        void Refresh2()
        {
            P.GameDir = Folder.Text.Trim();
            bool ok = P.GameDir.Length > 0 && File.Exists(Path.Combine(P.GameDir, "ISLAND.exe"));
            string ed = ok ? P.Edition : null;
            BInstall.Enabled = ok && ed != null;
            BRemove.Enabled = BKo.Enabled = BOrig.Enabled = ok && P.Installed;
            BPlay.Enabled = ok;
            if (!ok) State.Text = "ISLAND.exe 가 있는 게임 폴더를 골라 주세요.";
            else if (ed == null) State.Text = "이 폴더의 ISLAND 는 이 패치가 아는 판(일본어판·영어판)이 아닙니다.";
            else if (!P.Installed) State.Text = P.EditionLabel(ed) + " — 한국어 패치가 설치되어 있지 않습니다.";
            else if (P.InstalledEdition != null && P.InstalledEdition != ed) State.Text = P.EditionLabel(ed) + " — 설치된 한국어 파일이 다른 판용입니다. [설치 / 다시 설치]를 눌러 주세요.";
            else State.Text = P.EditionLabel(ed) + " — 설치됨, 지금 언어 " + (P.Language() == "ko" ? "한국어" : P.OriginalLabel);
        }

        void Run(Action a, bool showWarnings)
        {
            foreach (Control c in Controls) if (c is Button) c.Enabled = false;
            UseWaitCursor = true;
            try
            {
                a();
                if (showWarnings && P.Warnings.Count > 0)
                    MessageBox.Show(this, "설치했지만 확인할 것이 있습니다:\r\n\r\n- " + string.Join("\r\n- ", P.Warnings), Text, MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
            catch (Exception ex) { P.Log("오류: " + ex.Message); MessageBox.Show(this, ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error); }
            finally { UseWaitCursor = false; Refresh2(); }
        }
    }

    internal static class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            var exeDir = Path.GetDirectoryName(Application.ExecutablePath);
            Patcher p;
            try { p = new Patcher(exeDir); }
            catch (Exception ex) { MessageBox.Show("패치 파일(payload\\manifest.txt)을 읽지 못했습니다.\r\n" + ex.Message, "ISLAND 한국어 패치"); return 2; }
            string game = null, action = null, lang = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--game" && i + 1 < args.Length) game = args[++i];
                else if (args[i] == "--install") action = "install";
                else if (args[i] == "--uninstall") action = "uninstall";
                else if (args[i] == "--verify") action = "verify";
                else if (args[i] == "--edition") action = action ?? "edition";
                else if (args[i] == "--lang" && i + 1 < args.Length) { action = action ?? "lang"; lang = args[++i]; }
            }
            p.GameDir = game ?? Patcher.FindGame();
            if (action == null)
            {
                Application.EnableVisualStyles();
                Application.Run(new MainForm(p));
                return 0;
            }
            // console mode (automation / tests)
            var log = new StringBuilder();
            p.Log = s => log.AppendLine(s);
            int code = 0;
            try
            {
                if (p.GameDir == null) throw new InvalidOperationException("game folder not found");
                log.AppendLine("EDITION " + (p.Edition ?? "unknown"));
                log.AppendLine("STEAM " + (p.IsSteam ? "1" : "0") + " EXE " + p.ExeVersion() + " INSTALLED_FOR " + (p.InstalledEdition ?? "-"));
                if (action == "install") p.Install();
                else if (action == "uninstall") p.Uninstall();
                else if (action == "verify") p.CheckOriginals();
                if (lang != null) p.SetLanguage(lang);
                foreach (var w in p.Warnings) log.AppendLine("WARNING " + w);
            }
            catch (Exception ex) { log.AppendLine("ERROR " + ex.Message); code = 1; }
            File.WriteAllText(Path.Combine(exeDir, "setup-last.log"), log.ToString(), new UTF8Encoding(true));
            return code;
        }
    }
}
