"""Check Korean strings against the shared donor table (data/pua_table.json) and the 58-cell wrap.

The patch font only has the Hangul in the table; a character outside it would need a new font and
table for both editions. Prints only verdicts and counts unless --show is given (subagents only).
Usage: python -I check_ko_text.py <json file {key: korean}> [--show]
       python -I check_ko_text.py --text "<korean>" [--show]
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wrapsim  # noqa: E402
from kocodec import Codec, cp932_ok  # noqa: E402

DATA = os.path.join(os.path.dirname(HERE), "data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json", nargs="?")
    ap.add_argument("--text")
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    codec = Codec.load(os.path.join(DATA, "pua_table.json"))
    items = {"text": a.text} if a.text is not None else json.load(open(a.json, encoding="utf-8"))
    bad_total = 0
    for k, v in items.items():
        bad = sorted({c for c in v if c not in codec.enc and not (c in "\r\n" or cp932_ok(c))})
        wrapped, n = wrapsim.word_wrap(v, 58, 1, wrapsim.gog_units)
        rows = wrapped.replace("\\n", "\n").count("\n") + 1
        bad_total += len(bad)
        if a.show:
            print("%s: %s | lines after wrap: %d | not in table: %s" % (k, "OK" if not bad else "BAD", rows, "".join(bad) or "-"))
        else:
            print("%s: %s | lines after wrap: %d | chars not in table: %d" % (k, "OK" if not bad else "BAD", rows, len(bad)))
    print("total characters not in table:", bad_total)
    sys.exit(1 if bad_total else 0)


if __name__ == "__main__":
    main()
