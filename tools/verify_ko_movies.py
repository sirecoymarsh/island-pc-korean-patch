"""Decode check of the movies the patch changed (both builds): every changed .webm in the built movie.int is written
to a scratch folder, decoded in full by ffmpeg (-xerror: stop at the first decode error) and its decoded length
compared with the container's; the scratch copies are deleted. A movie that does not decode to its end could stop
the game where it plays. Prints names and numbers only. Usage: python -I verify_ko_movies.py"""
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"P:\AI\island-steam-ko\tools")
import cs2  # noqa: E402
import verify_ko_scene as v  # noqa: E402

FF = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\switch-native-port\tools\ffmpeg-8.1.2\ffmpeg.exe"
FP = FF.replace("ffmpeg.exe", "ffprobe.exe")
TMP = r"Y:\AI\claude-work\island-fullrun\movie-check"


def duration(path):
    out = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
                         capture_output=True, text=True).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return None


def decoded_seconds(path):
    """full decode of every stream; -> (returncode, seconds decoded, error lines)"""
    p = subprocess.run([FF, "-hide_banner", "-nostats", "-v", "error", "-xerror", "-threads", "4", "-i", path,
                        "-map", "0", "-f", "null", "-", "-progress", "pipe:1"],
                       capture_output=True, text=True, creationflags=0x00004000)   # BELOW_NORMAL_PRIORITY_CLASS
    secs = None
    for ln in p.stdout.splitlines():
        if ln.startswith("out_time_us="):
            try:
                secs = int(ln.split("=", 1)[1]) / 1e6
            except ValueError:
                pass
    errs = [ln for ln in p.stderr.splitlines() if ln.strip()]
    return p.returncode, secs, errs


def main():
    os.makedirs(TMP, exist_ok=True)
    bad = 0
    for label, o, kdir in v.BUILDS:
        key = cs2.crc_key(cs2.passphrase(os.path.join(o, "ISLAND.exe")))
        mo = v.open_kif(os.path.join(o, "movie.int"), key)
        mk = v.open_kif(os.path.join(kdir, "movie.int"), key)
        no = {e["name"].casefold(): e["name"] for e in mo.entries}
        for e in mk.entries:
            k = e["name"].casefold()
            data = mk.read(e["name"])
            if k in no and mo.read(no[k]) == data:
                continue
            path = os.path.join(TMP, label + "_" + e["name"])
            open(path, "wb").write(data)
            d = duration(path)
            rc, secs, errs = decoded_seconds(path)
            ok = rc == 0 and not errs and d and secs and secs >= d - 0.5
            bad += 0 if ok else 1
            print("%-8s %-20s container %6.1f s, decoded %6.1f s, rc %d, errors %d  %s" % (
                label, e["name"], d or -1, secs or -1, rc, len(errs), "OK" if ok else "PROBLEM " + " | ".join(errs[:2])[:200]),
                flush=True)
            os.remove(path)
    print("movies with a problem: %d" % bad)


if __name__ == "__main__":
    main()
