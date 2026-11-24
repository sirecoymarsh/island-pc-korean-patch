"""ko\\movie.int = Steam original movie.int with the main opening replaced by the version carrying
Codex's bilingual lyric subtitles (opening-ja-ko.ass burned in, VP8, original Vorbis audio copied).
Usage: python -I build_movie.py"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

ORIG = r"Y:\AI\island-steam-ko\steam-orig\movie.int"
OPENING = r"Y:\AI\island-steam-ko\work\movie\opmovie.ko.webm"
OUT = r"Y:\AI\island-steam-ko\build\ko\movie.int"


def main():
    from build_gog_ui import ko_movies   # endings + winter preview with Codex's subtitles (build_ko_movies.py)
    k = cs2.PlainKif(ORIG)
    repl = {"opmovie.webm": open(OPENING, "rb").read()}
    repl.update(ko_movies("steam"))
    total = k.write(OUT, repl)
    chk = cs2.PlainKif(OUT)
    ok = all(chk.read(n) == d for n, d in repl.items())
    same_others = all(chk.read(e["name"]) == k.read(e["name"]) for e in k.entries if e["name"] not in repl)
    print({"out": OUT, "bytes": total, "replaced": sorted(repl), "readback": ok, "other_movies_unchanged": same_others})


if __name__ == "__main__":
    main()
