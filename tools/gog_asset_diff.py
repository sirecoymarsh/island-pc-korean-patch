"""Which entries of every GOG archive differ from Steam JP (= English-localized or re-encoded)?
-> Y:\AI\island-steam-ko\gog-work\asset_diff.json (names and sizes only)."""
import hashlib
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402

G = r"Y:\AI\island-steam-ko\gog-orig"
S = r"Y:\AI\island-steam-ko\steam-orig"
OUT = r"Y:\AI\island-steam-ko\gog-work\asset_diff.json"


def open_kif(path, key):
    plain = open(path, "rb").read(19)[8:19] != b"__key__.dat"
    return cs2.PlainKif(path) if plain else cs2.Kif(path, key)


def main():
    kg = cs2.crc_key(cs2.passphrase(os.path.join(G, "ISLAND.exe")))
    ks = cs2.crc_key(cs2.passphrase(os.path.join(S, "ISLAND.exe")))
    res = {}
    for fn in sorted(os.listdir(G)):
        if not fn.endswith(".int"):
            continue
        a = open_kif(os.path.join(G, fn), kg)
        b = open_kif(os.path.join(S, fn), ks)
        diff, only_g, same = [], [], 0
        with open(a.path, "rb") as fa, open(b.path, "rb") as fb:
            for e in a.entries:
                k = e["name"].casefold()
                if k not in b.by_name:
                    only_g.append(e["name"])
                    continue
                eb = b.by_name[k]
                if e["size"] == eb["size"] and hashlib.sha1(a.read(e["name"], fa)).digest() == hashlib.sha1(b.read(eb["name"], fb)).digest():
                    same += 1
                else:
                    diff.append([e["name"], e["size"], eb["size"]])
        only_s = sorted({e["name"].casefold() for e in b.entries} - {e["name"].casefold() for e in a.entries})
        res[fn] = {"entries": len(a.entries), "same": same, "differ": diff, "only_gog": only_g, "only_steam": only_s}
        print(fn, len(a.entries), "same", same, "differ", len(diff), "only_gog", len(only_g), "only_steam", len(only_s), flush=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
