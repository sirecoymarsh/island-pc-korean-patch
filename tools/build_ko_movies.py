"""Korean-subtitled PC versions of the four ending movies and the winter preview.

Subtitles: Codex's bilingual (JP above, KR below) ASS made for the Switch `_en` movies
(cg-opening-20261101\\추가영상자막-20261102\\자막원본, 136 cues, user-approved lyric source).
Measured 11-07 by audio cross-correlation: the PC movies line up with the Switch ones exactly,
except edmovie2_kar which is +0.0333 s on PC (Codex's kar ASS is shifted by that here).
Rendering is Codex's: endings scaled to 1024x576 at x128 with a black 144 px subtitle footer
(the credits in the picture stay as they are, as on Switch), the preview keeps the full frame.
Encoded once from each edition's own movie (Steam: Japanese credits, GOG: English credits) to
VP8 (the PC engine's decoder plays VP8 only), 2-pass, no alt-ref (hidden) frames - like the
opening that played in game - so the packet count equals the source; Vorbis audio copied untouched.

Never prints subtitle text. Runs ffmpeg below normal priority with 4 threads.
Usage: python -I build_ko_movies.py [--edition steam|gog] [--only NAME] [--check-frame]"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"Y:\AI\island-steam-ko"
PC = os.path.join(ROOT, "work", "movie", "pc")
OUT = os.path.join(ROOT, "work", "movie", "ko")
ASS_OUT = os.path.join(ROOT, "work", "movie", "ass")
CG = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\cg-opening-20261101"
ASS_SRC = os.path.join(CG, "추가영상자막-20261102", "자막원본")
FF = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\switch-native-port\tools\ffmpeg-8.1.2\ffmpeg.exe"
FP = FF.replace("ffmpeg.exe", "ffprobe.exe")
NAMES = ["opmovie_win", "edmovie2_kar", "edmovie2_lin", "edmovie2_sar", "edmovie3"]
SHIFT = {"edmovie2_kar": 0.0333}
BELOW_NORMAL = 0x00004000


def kbps(p):
    o = subprocess.run([FP, "-v", "error", "-show_entries", "format=bit_rate", "-of", "csv=p=0", p], capture_output=True, text=True)
    return int(o.stdout.strip()) // 1000


def shift_ass(src, dst, sec):
    """copy the ASS with every Dialogue start/end moved by sec (text untouched, never printed)"""
    t = open(src, encoding="utf-8-sig").read()

    def fmt(x):
        cs = max(0, int(round(x * 100)))
        return "%d:%02d:%02d.%02d" % (cs // 360000, cs // 6000 % 60, cs // 100 % 60, cs % 100)

    def parse(s):
        h, m, r = s.split(":")
        return int(h) * 3600 + int(m) * 60 + float(r)

    def fix(m):
        return "%s%s,%s,%s" % (m.group(1), fmt(parse(m.group(2)) + sec), fmt(parse(m.group(3)) + sec), m.group(4))

    t2, n = re.subn(r"(?m)^(Dialogue:\s*[^,]*,)([^,]+),([^,]+),(.*)$", fix, t)
    open(dst, "w", encoding="utf-8-sig", newline="").write(t2)
    return n


def vf(name, ass_name):
    f = []
    if name.startswith("ed"):
        f += ["scale=1024:576:flags=lanczos", "pad=1280:720:128:0:color=black"]
    f.append("ass=%s" % ass_name)
    return ",".join(f)


def run(cmd, log):
    with open(log, "a", encoding="utf-8") as fh:
        fh.write("\n$ " + " ".join(cmd) + "\n")
        fh.flush()
        p = subprocess.run(cmd, cwd=ASS_OUT, stdout=fh, stderr=fh, creationflags=BELOW_NORMAL)
    if p.returncode:
        raise SystemExit("ffmpeg failed (%d), see %s" % (p.returncode, log))


def audio_md5(p):
    o = subprocess.run([FF, "-v", "error", "-i", p, "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"], capture_output=True, text=True)
    return o.stdout.strip()


def frame_count(p):
    o = subprocess.run([FP, "-v", "error", "-count_packets", "-select_streams", "v:0", "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return int(o.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--edition", choices=["steam", "gog"])
    ap.add_argument("--only")
    ap.add_argument("--check-frame", action="store_true", help="render one frame per movie at a cue time only")
    a = ap.parse_args()
    os.makedirs(ASS_OUT, exist_ok=True)
    for n in NAMES:
        cues = shift_ass(os.path.join(ASS_SRC, n + "_en.ja-ko.ass"), os.path.join(ASS_OUT, n + ".ja-ko.ass"), SHIFT.get(n, 0.0))
    report_path = os.path.join(OUT, "report.json")
    report = json.load(open(report_path, encoding="utf-8")) if os.path.exists(report_path) else {}
    for ed in ([a.edition] if a.edition else ["gog", "steam"]):
        os.makedirs(os.path.join(OUT, ed), exist_ok=True)
        for n in NAMES:
            if a.only and n != a.only:
                continue
            src = os.path.join(PC, ed, n + ".webm")
            dst = os.path.join(OUT, ed, n + ".webm")
            log = os.path.join(OUT, ed, n + ".log")
            if a.check_frame:
                t = {"opmovie_win": 12.5, "edmovie2_kar": 30.0, "edmovie2_lin": 30.0, "edmovie2_sar": 30.0, "edmovie3": 40.0}[n]
                png = os.path.join(OUT, ed, n + ".check.png")
                run([FF, "-hide_banner", "-y", "-i", src, "-vf", "setpts=PTS,%s" % vf(n, n + ".ja-ko.ass"), "-ss", str(t), "-frames:v", "1", "-update", "1", png], log)
                print(ed, n, "check frame written")
                continue
            target = int(kbps(src) * (1.25 if n.startswith("op") else 1.1))
            tmp = dst + ".part.webm"
            passlog = os.path.join(OUT, ed, n + "-2pass")
            common = [FF, "-hide_banner", "-y", "-i", src, "-map", "0:v:0", "-map", "0:a:0", "-vf", vf(n, n + ".ja-ko.ass"),
                      "-c:v", "libvpx", "-b:v", "%dk" % target, "-deadline", "good", "-cpu-used", "1", "-auto-alt-ref", "0",
                      "-lag-in-frames", "0", "-threads", "4", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-passlogfile", passlog]
            run(common + ["-pass", "1", "-an", "-f", "webm", os.devnull], log)
            run(common + ["-pass", "2", "-c:a", "copy", "-f", "webm", tmp], log)
            xerr = subprocess.run([FF, "-v", "error", "-xerror", "-i", tmp, "-f", "null", "-"], capture_output=True, text=True)
            rec = {"edition": ed, "source_kbps": kbps(src), "target_kbps": target, "out_kbps": kbps(tmp), "bytes": os.path.getsize(tmp),
                   "frames_src": frame_count(src), "frames_out": frame_count(tmp), "audio_md5_same": audio_md5(src) == audio_md5(tmp),
                   "decode_xerror_ok": xerr.returncode == 0 and not xerr.stderr.strip(), "subtitle_cues": cues,
                   "ass_shift_s": SHIFT.get(n, 0.0)}
            ok = rec["frames_src"] == rec["frames_out"] and rec["audio_md5_same"] and rec["decode_xerror_ok"]
            rec["ok"] = ok
            if ok:
                os.replace(tmp, dst)
                rec["sha256"] = hashlib.sha256(open(dst, "rb").read()).hexdigest()
            report["%s/%s" % (ed, n)] = rec
            json.dump(report, open(report_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(ed, n, json.dumps({k: rec[k] for k in ("target_kbps", "out_kbps", "frames_src", "frames_out", "audio_md5_same", "decode_xerror_ok", "ok")}), flush=True)


if __name__ == "__main__":
    main()
