"""Japanese-mode check of the same install: language=ja -> no redirects, original font,
exit message box decoded as Unicode Japanese. Title screen only (no story)."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gamectl  # noqa: E402
import testenv  # noqa: E402

ROOT = r"Y:\AI\island-steam-ko"
SHOTS = os.path.join(ROOT, "shots", "ja")
INI = os.path.join(ROOT, "testgame", "island-ko.ini")


def main():
    os.makedirs(SHOTS, exist_ok=True)
    with open(INI, "w", encoding="ascii") as f:
        f.write("[ISLAND-KO]\r\nlanguage=ja\r\n")
    g = None
    try:
        g = testenv.start()
        if not g or not g.hwnd:
            print("no window"); return
        time.sleep(22)
        g.shot(os.path.join(SHOTS, "title_ja.png"))
    finally:
        left = testenv.finish(g)
        with open(INI, "w", encoding="ascii") as f:
            f.write("[ISLAND-KO]\r\nlanguage=ko\r\n")
        log = testenv.read_log()
        print("left", left)
        for line in log:
            if not line.startswith("font face") or "ISLAND KO" in line:
                print("  LOG", line[:200])
        print("redirects:", sum("redirect" in l for l in log), "font overrides:", sum("-> ISLAND KO" in l for l in log))


if __name__ == "__main__":
    main()
