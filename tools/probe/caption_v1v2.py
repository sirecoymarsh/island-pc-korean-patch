"""Did Codex fix the caption code between v1 (built for Steam+GOG) and v2 (GOG, run in game)?
Compares the caption-related non-text code of v1/gog vs v2/gog and v1/steam vs v1/gog."""
import os, re, sys, zlib, difflib, struct
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
S = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\system-voice-staging"


def load(path):
    b = open(path, "rb").read()
    return zlib.decompress(b[16:]).decode("cp932", "replace")


def code_only(t):
    # caption-related lines, text masked
    out = []
    for l in t.splitlines():
        if re.search(r"KO_CAP|\\210|cap|CAP", l):
            out.append(re.sub(r"[^\x00-\x7f]+", "~", l))
    return out


for name in ["title.fes", "meswnd.fes", "omake_sysvoice.fes"]:
    a = code_only(load(os.path.join(S, "v1", "gog", "logical", name)))
    b = code_only(load(os.path.join(S, "v2", "gog", "logical", name)))
    c = code_only(load(os.path.join(S, "v1", "steam", "logical", name)))
    d1 = [l for l in difflib.unified_diff(a, b, lineterm="", n=0) if not l.startswith(("---", "+++", "@@"))]
    d2 = [l for l in difflib.unified_diff(a, c, lineterm="", n=0) if not l.startswith(("---", "+++", "@@"))]
    print("==", name, "caption lines v1gog", len(a), "v2gog", len(b), "v1steam", len(c), "| v1->v2 changes", len(d1), "| gog->steam changes", len(d2))
    for l in d1[:12]:
        print("   v1->v2:", l[:150])
# show the caption subroutine definitions once (masked)
t = load(os.path.join(S, "v1", "steam", "logical", "title.fes"))
i = t.find("#KO_CAP_SHOW")
print("---- KO_CAP block (masked) ----")
print(re.sub(r"[^\x00-\x7f]+", "~", t[i:i + 1600]) if i >= 0 else "no #KO_CAP_SHOW label")
