"""Clean copy of the GOG/English ISLAND (engine 2.6.1.80, no DRM) for builds and hashes.

Source files: Codex's extracted installation folder (read only). Every file is checked against the
CRC32 recorded in the original ZIP; config\\startup.xml is taken from the ZIP itself because the
installation copy's save path was edited by Codex on 10-28.
  -> Y:\\AI\\island-steam-ko\\gog-orig  + gog-orig.json (sha256 of every file)
Usage: python -I gog_snapshot.py"""
import hashlib
import json
import os
import shutil
import sys
import zipfile
import zlib

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SRC = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\installation\ISLAND"
ZIP = r"F:\DOWN\ISLAND.zip"
PREFIX = "ISLAND/ISLAND/"
OUT = r"Y:\AI\island-steam-ko\gog-orig"
FROM_ZIP = {"config/startup.xml"}


def crc_sha(path):
    c = 0
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            c = zlib.crc32(b, c)
            h.update(b)
    return c & 0xFFFFFFFF, h.hexdigest()


def main():
    z = zipfile.ZipFile(ZIP)
    members = {i.filename[len(PREFIX):]: i for i in z.infolist() if i.filename.startswith(PREFIX) and not i.is_dir()}
    os.makedirs(OUT, exist_ok=True)
    manifest = {"source": SRC, "zip": ZIP, "files": {}}
    bad = []
    for rel, info in sorted(members.items()):
        dst = os.path.join(OUT, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if rel in FROM_ZIP:
            with z.open(info) as s, open(dst, "wb") as d:
                shutil.copyfileobj(s, d)
        elif not (os.path.exists(dst) and os.path.getsize(dst) == info.file_size):
            shutil.copy2(os.path.join(SRC, rel.replace("/", os.sep)), dst)
        crc, sha = crc_sha(dst)
        if crc != info.CRC or os.path.getsize(dst) != info.file_size:
            bad.append(rel)
        manifest["files"][rel] = {"size": info.file_size, "crc32": "%08x" % info.CRC, "sha256": sha}
    manifest["crc_mismatch"] = bad
    json.dump(manifest, open(OUT + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"files": len(members), "crc_mismatch": bad, "exe_sha256": manifest["files"]["ISLAND.exe"]["sha256"][:16]}))


if __name__ == "__main__":
    main()
