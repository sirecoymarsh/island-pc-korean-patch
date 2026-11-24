"""Build the Korean text archives for Steam ISLAND (JP depot 857454, build 3508164).

  scene.int   : 499 CSTs, every kit entry (JP0001-JP0487, review/out first) in Korean
  fes.int     : original + Codex Korean UI FES (5 files) re-encoded with our PUA table
  config.int  : original + Codex Korean startup.xml / startup_master.xml (font -> ours,
                save path and sound focus setting back to the original values)
  config/startup.xml (loose) : same treatment

Prints counts only - never script text (the user is playing the story for the first time).
Usage: python -I build_text.py [--out DIR] [--test-save DIR]
"""
import argparse
import difflib
import json
import os
import re
import sys
import zlib
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cs2  # noqa: E402
import kit  # noqa: E402
import wrapsim  # noqa: E402
from kocodec import RINNE_ALIAS, RINNE_DOT, Codec, codex_decoder  # noqa: E402

ORIG = r"Y:\AI\island-steam-ko\steam-orig"
CODEX_PAYLOAD = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\delivery\ISLAND-UI-local-20261028-9d6dd068\payload\ko"
CODEX_MAP = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\text-font\encoding_map.json"
DATA = os.path.join(os.path.dirname(HERE), "data")
PUA_TABLE = os.path.join(DATA, "pua_table.json")
FONT_FAMILY = "ISLAND KO"
CODEX_FAMILY = "ISLAND UI Korean"

CODE = re.compile(r"\\(?:fll|fl|fs|fn|pc|pl|pr|n|r|m|@|w\d+;|f\d+;)")
RUBY = re.compile(r"\[([^\[\]]*)\]")
JPCHARS = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\u4e00-\u9fff\uff66-\uff9f]")
CODEX_FES = ["conf_text.fes", "load.fes", "save.fes", "select.fes", "select_route.fes"]


def fes_unpack(blob):
    magic, comp, uncomp, z = __import__("struct").unpack_from("<4sIII", blob)
    assert magic == b"FES\0" and len(blob) == 16 + comp
    data = zlib.decompress(blob[16:])
    assert len(data) == uncomp
    return data, z


def fes_pack(data, z=0):
    import struct
    comp = zlib.compress(data, 9)
    return b"FES\0" + struct.pack("<III", len(comp), len(data), z) + comp


# Codex's system-voice caption (10-28) draws its words into the STRING object while it is still
# hidden (clear, pos, str, draw -1, THEN disp 1); the engine does not render text into a hidden
# STRING, so only the dark band (ko_cap_bg) showed (11-08 user: menu captions missing, a black
# band flashes when changing settings tabs). The original scripts' STRING objects are displayed
# before they draw. Fix: show band and text first, then clear/pos/str/draw (GOG copy 11-08: the
# Korean line renders, centred by its \pc).
_CAP_BLOCK = re.compile(r"(?m)^(ko_cap_text clear(\r?)\nko_cap_text pos [^\r\n]*\r?\nko_cap_text str [^\r\n]*\r?\nko_cap_text draw -1\r?\n)"
                        r"ko_cap_text disp 1\r?\nko_cap_bg disp 1(\r?)$")


# 11-08 user: the band is not needed -> an option. Global $1001 = 1 shows the band; default 0 = text
# only, with an outline (layout shadow 1 1) so the words stay readable on bright screens.
# (First built with $1020, which looked unused but is $(DLGSKIP_DEF+DLGNO_FLOW) = 1011+9, the
# 「플로차트에서 점프 시 확인」 switch of dialog.fes/conf_dialog.fes - computed indices; 11-08 moved.
# Free globals were recounted with macros and $(...) indices resolved: 1001-1010 and 903-989 unused.)
CAPBG_VAR = "$1001"


# Codex keeps the caption state in the locals \210 (caption id), \211 (state), \212 (start frame), \213
# (elapsed). The original scripts never name those, but computed slots reach them: the CG gallery
# keeps its 12 thumbnails' CG numbers in \(200+slot), so slots 10/11 overwrote the caption id and
# state - a wrong caption showed ("자막은 뜨는데 음성은 안나오네", 11-08) and a thumbnail's CG number
# could be reset by the caption code. Moved to \290-\293: no script names or reaches 260-299
# (literal locals stop at 259 below 300; computed bases 250 reach about 258, 300 starts at 300).
CAP_LOCAL_MOVE = {210: 290, 211: 291, 212: 292, 213: 293}


def caption_locals(text):
    """-> (text, renamed references) - only in scripts that carry Codex's captions"""
    if "ko_cap_text" not in text:
        return text, 0
    return re.subn(r"\\(21[0-3])(?!\d)", lambda m: "\\%d" % CAP_LOCAL_MOVE[int(m.group(1))], text)


# 11-08 user (sound tab): 「시스템 보이스 앞에 2명만 자막이 뜨고 마지막 애는 안떠. 그리고 개인당 자막 대사도
# 떠야 하는데 플레이 눌러도 안떠」. The tab plays its own voices, outside Codex's se1 menu captions:
#   #SYSVOICE_DECIDE  snd_setest     <set>_sysvoice_025   picking a system-voice character ($820 0..5)
#   #VOICE_TEST       snd_voicetest  <char>_sysvoice_026  the ▶ next to a character's volume (\1 0..15;
#                                    14/15 = Y_test_001 / X_test_001, the male / female "others")
#   #VOICE_RESET      snd_voicetest  <char>_sysvoice_027  a character's voice switched back on (\0 0..13)
# A sample that is the very recording of a captioned menu voice (SAMPLE_SAME: byte-identical files in
# pcm_*.int and se.int) takes that caption id. The others get caption blocks from
# data\sample_captions_ko.json: the samples of the non-system-voice characters are byte copies of story
# voices and carry our translation of that story line; Sara's own recordings (Codex had no se_sars_025 /
# se_sarw_025 - no caption, the reported "third one") and the rest of the winter set's were transcribed
# with the local ASR and translated (11-08).
# The caption starts in the sound's PLAY event from a pending id (\294, free like \290-\293). A sound object's
# STOP event comes when its fade-out ends (~0.15 s after `stop`, test DLL sound log 11-08) - after the next
# sample's PLAY - so a STOP hides the caption only when that object started it (\295: 1 snd_setest,
# 2 snd_voicetest; se1.PLAY clears it) and the caption is older than CAP_STOP_GUARD frames; every handler
# that starts a sample hides the old caption itself first (call SYSVOICE_STOP).
# Switching a character's voice back on runs `setconf 1 play 3 n` just before its 027 sample; the caption drawn
# in that frame stays shown but its text never appears (test copy 11-08: PLAY handled, no hide until the end,
# caption area unchanged) - the setconf seems to wipe the STRING's texture. So a sample caption is drawn once
# more CAP_REDRAW frames after it starts (\296 = 1: KO_CAP_TICK forces the current cue again).
SAMPLE_CAPTIONS = os.path.join(DATA, "sample_captions_ko.json")
SAMPLE_SAME = {"lins_sysvoice_025": "se_lins_025", "lins_sysvoice_026": "se_lins_026", "lins_sysvoice_027": "se_lins_027",
               "kars_sysvoice_025": "se_kars_025", "kars_sysvoice_026": "se_kars_026", "kars_sysvoice_027": "se_kars_027",
               "linw_sysvoice_025": "se_linw_025", "karw_sysvoice_025": "se_karw_025", "karw_sysvoice_027": "se_karw_026",
               "sarw_sysvoice_027": "se_sarw_026"}
CAP_PENDING = "\\294"
CAP_OWNER = "\\295"
CAP_STOP_GUARD = 30
CAP_REDRAW_FLAG = "\\296"
CAP_REDRAW = 10
SOUND_HANDLERS =[("#SYSVOICE_DECIDE", "snd_setest", "$820"), ("#VOICE_TEST", "snd_voicetest", "\\1"),
                  ("#VOICE_RESET", "snd_voicetest", "\\0")]


def _cap_block(cid, cues):
    """one caption in Codex's KO_CAP_TICK form (as caption_fix leaves it): latest cue first, 60 frames a second"""
    out = ["if (\\290==%d)" % cid]
    for k in range(len(cues) - 1, -1, -1):
        t = cues[k]["text"]
        if not t or re.search(r"[\\\[\]{}$#\r\n\t]", t):
            raise SystemExit("sample caption %d: text not usable in a FES str line" % cid)
        out += ["if (\\293>=%d)" % int(round(cues[k]["start"] * 60)), "if (\\291!=%d)" % k, "\\291 = %d" % k,
                "if (%s==1)" % CAPBG_VAR, "ko_cap_bg disp 1", "endif", "ko_cap_text disp 1", "ko_cap_text clear",
                "ko_cap_text pos 48 644", "ko_cap_text str \\pc" + t, "ko_cap_text draw -1", "endif", "break", "endif"]
    return out + ["endif"]


def decide_caption(text, data=None):
    """conf_sound.fes (both builds, after caption_fix): captions for the sound tab's own voice plays - the
    system-voice choice, the ▶ samples and the voice-on samples (see above). Returns (text, edits).
    Codex's Steam scripts mix line ends (its added lines end in LF inside CRLF files), so lines are
    split on LF and each new line takes the line end of the line it is put next to."""
    if data is None:
        data = json.load(open(SAMPLE_CAPTIONS, encoding="utf-8"))["captions"]
    L = text.split("\n")
    S = [s.rstrip("\r").strip() for s in L]

    def block(label):
        if S.count(label) != 1:
            raise SystemExit("conf_sound.fes: %s found %d times" % (label, S.count(label)))
        d = S.index(label)
        return d, next((n for n in range(d + 1, len(S)) if S[n].startswith("#")), len(S))

    # Codex's caption id of each menu voice (#SYSVOICE: "se1 load <se>" then "\290 = <id>")
    i, j = block("#SYSVOICE")
    se_id, last = {}, None
    for s in S[i:j]:
        m = re.match(r"se1 load (\S+)$", s)
        if m:
            last = m.group(1)
        m = re.match(r"\\290 = (\d+)$", s)
        if m and last:
            if int(m.group(1)):
                se_id[last] = int(m.group(1))
            last = None
    i, j = block("#KO_CAP_TICK")
    top = max(int(m.group(1)) for m in (re.match(r"if \(\\290==(\d+)\)$", s) for s in S[i:j]) if m)
    ids, new = {}, []
    for name in sorted(set(SAMPLE_SAME) | set(data)):
        if name in SAMPLE_SAME and SAMPLE_SAME[name] in se_id:
            ids[name] = se_id[SAMPLE_SAME[name]]
        elif name in data:
            top += 1
            ids[name] = top
            new.append((top, data[name]["cues"]))
        else:
            raise SystemExit("sample %s: Codex caption %s missing" % (name, SAMPLE_SAME[name]))
    for label in ("#snd_setest.PLAY", "#snd_setest.STOP", "#snd_voicetest.PLAY", "#snd_voicetest.STOP"):
        if label in S:
            raise SystemExit("conf_sound.fes: %s already there" % label)
    edits = []   # (index to insert at, lines, index of the line whose line end they take)
    e = block("#KO_CAP_END")[0]
    edits.append((e, [x for cid, cues in new for x in _cap_block(cid, cues)], e))
    played = 0
    for label, snd, var in SOUND_HANDLERS:
        d, f = block(label)
        pairs, cur = {}, None
        for s in S[d:f]:
            m = re.match(r"if \(%s==(\d+)\)$" % re.escape(var), s)
            if m:
                cur = int(m.group(1))
            m = re.match(r"%s load (\S+)$" % snd, s)
            if m and cur is not None:
                pairs[cur] = m.group(1)
        p = [n for n in range(d, f) if S[n] == "%s play 1 1" % snd]
        if len(p) != 1 or not pairs:
            raise SystemExit("conf_sound.fes: %s not in the expected form" % label)
        lines = ["%s = 0" % CAP_PENDING]
        for v, name in sorted(pairs.items()):
            if name in ids:
                lines += ["if (%s==%d)" % (var, v), "%s = %d" % (CAP_PENDING, ids[name]), "endif"]
                played += 1
        edits.append((p[0], lines, p[0]))   # before the play: its PLAY event may be handled at once
    d, f = block("#SOUND_TEST")
    edits.append((d + 1, ["%s = 0" % CAP_PENDING], d))   # the SE / master volume tests carry no caption
    d, f = block("#se1.PLAY")
    edits.append((d + 1, ["%s = 0" % CAP_OWNER], d))     # a menu voice caption belongs to no sample
    d, f = block("#KO_CAP_TICK")
    el = [n for n in range(d, f) if S[n] == "\\293 = _FRAME_-\\292"]
    if len(el) != 1:
        raise SystemExit("conf_sound.fes: KO_CAP_TICK elapsed line not found once")
    edits.append((el[0] + 1, ["if (%s==1)" % CAP_REDRAW_FLAG, "if (\\293>=%d)" % CAP_REDRAW, "%s = 0" % CAP_REDRAW_FLAG,
                              "\\291 = -1", "endif", "endif"], el[0]))
    for at, lines, like in sorted(edits, key=lambda x: -x[0]):
        cr = "\r" if L[like].endswith("\r") else ""
        L[at:at] = [x + cr for x in lines]
    cr = "\r" if L[0].endswith("\r") else ""
    tail = []
    for k, snd in ((1, "snd_setest"), (2, "snd_voicetest")):
        tail += ["#%s.PLAY" % snd, "if (%s!=0)" % CAP_PENDING, "\\290 = %s" % CAP_PENDING, "%s = 0" % CAP_PENDING,
                 "%s = %d" % (CAP_OWNER, k), "%s = 1" % CAP_REDRAW_FLAG, "\\291 = -1", "\\292 = _FRAME_", "call KO_CAP_INIT",
                 "call KO_CAP_TICK", "endif",
                 "#%s.STOP" % snd, "if (%s==%d)" % (CAP_OWNER, k), "\\293 = _FRAME_-\\292",
                 "if (\\293>=%d)" % CAP_STOP_GUARD, "%s = 0" % CAP_OWNER, "call KO_CAP_HIDE", "endif", "endif"]
    tail = [x + cr for x in tail]
    if L and L[-1] == "":
        L[-1:-1] = tail
    else:
        if L and not L[-1].endswith("\r") and cr:
            L[-1] += cr
        L += tail + [""]
    return "\n".join(L), len(new) + played


# 11-09 (user 「시스템 자막들에 누가 말하는지 대사를 쓸까? 린네, 카렌: 이런식으로」): every caption of a system-voice
# character (the menu voices and that character's sound-tab samples) starts with the speaker - 「린네: …」. The
# speaker comes from the voice file: Codex's menu voices (#SYSVOICE: se1 load se_<code>_<n>, then \290 = id) and
# the sound tab's samples (handler: <snd> load <code>_sysvoice_<n> under `if (<var>==v)`, then our pending id).
# Codes lins/linw 린네, kars/karw 카렌, sars/sarw 사라 (summer / winter sets; the story's name boxes for these voices
# give the same names). The other characters' ▶ samples play next to their own labelled row and are left alone.
SPEAKERS = {"lins": "린네", "linw": "린네", "kars": "카렌", "karw": "카렌", "sars": "사라", "sarw": "사라"}


def _speaker_of(fname):
    m = re.match(r"(?:se_)?([a-z]+)_", fname)
    return SPEAKERS.get(m.group(1)) if m else None


def caption_speakers(text):
    """-> (text, caption str lines given a speaker); scripts without captions are returned as is"""
    if "ko_cap_text" not in text or "#KO_CAP_TICK" not in text:
        return text, 0
    L = text.split("\n")
    S = [s.rstrip("\r").strip() for s in L]
    who = {}

    def section(label):
        if label not in S:
            return None
        d = S.index(label)
        return d, next((n for n in range(d + 1, len(S)) if S[n].startswith("#")), len(S))

    sv = section("#SYSVOICE")
    if sv:
        last = None
        for s in S[sv[0]:sv[1]]:
            m = re.match(r"se1 load (\S+)$", s)
            if m:
                last = m.group(1)
            m = re.match(r"\\290 = (\d+)$", s)
            if m and last:
                if int(m.group(1)) and _speaker_of(last):
                    who[int(m.group(1))] = _speaker_of(last)
                last = None
    for label, snd, var in SOUND_HANDLERS:
        sec = section(label)
        if not sec:
            continue
        files, cur, pend = {}, None, {}
        for s in S[sec[0]:sec[1]]:
            m = re.match(r"if \(%s==(\d+)\)$" % re.escape(var), s)
            if m:
                cur = int(m.group(1))
            m = re.match(r"%s load (\S+)$" % snd, s)
            if m and cur is not None:
                files[cur] = m.group(1)
            m = re.match(r"%s = (\d+)$" % re.escape(CAP_PENDING), s)
            if m and cur is not None and int(m.group(1)):
                pend[cur] = int(m.group(1))
        for v, cid in pend.items():
            if _speaker_of(files.get(v, "")):
                who[cid] = _speaker_of(files[v])
    tick = section("#KO_CAP_TICK")
    n, cur = 0, None
    for i in range(tick[0], tick[1]):
        m = re.match(r"if \(\\290==(\d+)\)$", S[i])
        if m:
            cur = int(m.group(1))
            continue
        if cur in who and S[i].startswith("ko_cap_text str \\pc"):
            body = S[i][len("ko_cap_text str \\pc"):]
            if body.startswith(who[cur] + ": "):
                raise SystemExit("caption %d already carries its speaker" % cur)
            cr = "\r" if L[i].endswith("\r") else ""
            lead = L[i][:len(L[i]) - len(L[i].lstrip())]
            L[i] = lead + "ko_cap_text str \\pc" + who[cur] + ": " + body + cr
            n += 1
    return "\n".join(L), n


def caption_fix(text):
    """-> (text, caption draw blocks reordered); a script without captions is returned as is.
    The caption state locals are moved too (caption_locals)."""
    text = caption_locals(text)[0]
    eol = "\r\n" if "\r\n" in text else "\n"
    t, n = _CAP_BLOCK.subn(lambda m: "if (%s==1)%s\nko_cap_bg disp 1%s\nendif%s\nko_cap_text disp 1%s\n%s"
                           % (CAPBG_VAR, m.group(2), m.group(2), m.group(2), m.group(2), m.group(1)[:-1 - len(m.group(2))] + m.group(3)), text)
    if "ko_cap_text" in text and (n == 0 or n != text.count("ko_cap_text draw -1")):
        raise SystemExit("caption draw blocks not in the expected form (%d of %d)" % (n, text.count("ko_cap_text draw -1")))
    if n:
        t, k = re.subn(r"(?m)^ko_cap_text layout shadow 0 1(\r?)$", lambda m: "ko_cap_text layout shadow 1 1" + m.group(1), t)
        if k != 1:
            raise SystemExit("caption shadow line not found once (%d)" % k)
    return t, n


def sound_tab_option(text):
    """conf_sound.fes: checkbox btn_check[3] "자막 배경" (frames 703/713/753/763, help 1440 - see
    build_ui_option.py) right of "시스템 보이스", stored in CAPBG_VAR. Returns (text, insertions)."""
    eol = "\r\n" if "\r\n" in text else "\n"
    L = text.split(eol)
    v = CAPBG_VAR
    done = 0

    def find(line, start=0):
        hits = [i for i in range(start, len(L)) if L[i].strip() == line]
        if not hits:
            raise SystemExit("conf_sound.fes: line not found: " + line)
        return hits[0]

    def block(label):
        i = find(label)
        j = i + 1
        while j < len(L) and not L[j].strip().startswith("#"):
            j += 1
        return i, j

    i = find("BUTTON btn_check[3]"); L[i] = L[i].replace("btn_check[3]", "btn_check[4]"); done += 1
    i = find("btn_check[2] sys_sound 702 712 752 762 pl_base 1 737"); L.insert(i + 1, "btn_check[3] sys_sound 703 713 753 763 pl_base 1 738"); done += 1
    i = find("btn_check[0] 1,0,0"); L.insert(i + 1, "btn_check[3] 1,1,0"); done += 1
    i, j = block("#SET_NOWDATA_SKIPMO")
    k = [x for x in range(i, j) if L[x].strip() == "btn_check[BTN_M_SKIP] setid \\27"]
    if len(k) != 1:
        raise SystemExit("conf_sound.fes: SET_NOWDATA_SKIPMO not in the expected form")
    L.insert(k[0] + 1, "btn_check[3] setid %s" % v); done += 1
    i = find("#PUSH_SYSVOBTN")
    L[i:i] = ["if (_CLICK_L_==btn_check[3])", "$814 = 900", "call SYSVOICE", "if (%s==0)" % v, "%s = 1" % v, "else",
              "%s = 0" % v, "endif", "btn_check[3] setid 2+%s" % v, "endif"]; done += 1
    i, j = block("#btn_check.FOCUS")
    k = [x for x in range(i, j) if L[x].strip() == "img_text setid 0"]
    if not k:
        raise SystemExit("conf_sound.fes: btn_check.FOCUS not in the expected form")
    L[k[-1]:k[-1]] = ["if (@==3)", "btn_check[@] setid 2+%s" % v, "img_text settbl 0 1440", "endif"]; done += 1
    i, j = block("#btn_check.UNFOCUS")
    L[j:j] = ["if (@==3)", "btn_check[@] setid %s" % v, "endif"]; done += 1
    i, j = block("#SET_DEFAULT")
    k = [x for x in range(i, j) if L[x].strip() == "\\27 = 0"]
    if len(k) != 1:
        raise SystemExit("conf_sound.fes: SET_DEFAULT not in the expected form")
    L.insert(k[0] + 1, "%s = 0" % v); done += 1
    return eol.join(L), done


# 11-08 user: 「모든 콘텐츠 해방/다시 잠그기/초기화」, "가능하면 옵션에 넣어서 자연스런 게임 옵션의 하나로".
# Two rows of the 「확인 창」 settings tab (frames from build_ui_qa.py): 「모든 콘텐츠 열어 보기」 and
# 「처음 상태로 보기」, exclusive; both off = the real records. A view only (vn-qol standard (가)): the
# extras, flowchart and title scripts read view copies of the unlock flags made at their #START; no
# record is ever written. QA_VAR is put back to 0 at every start (flow.fes #GO_LOGO), like the Switch
# port's 검수 보기 (this run only). Turning everything open asks first (dialog number 14, frame 24).
QA_VAR = "$1002"                               # 0 real records, 1 everything open (view only)
# 11-09 (user 「저 기능은 게임의 상태를 설치 초기로 돌리는거야 그렇게 작동하게 해줘」): row 12 is no longer a "new game"
# view but 「처음 상태로 되돌리기」 - a real reset of the seen-records to the install state at the next start, done by
# the loader DLL on savegen.dat (backup kept; turning the row off brings the backup back). $1003 = 1 in the reset
# savegen.dat is the row's check. The screen asks (dialog 15 reset / 16 back), sends `opensite http islandko-reset`
# or `-restore` (the DLL catches it, nothing is opened) and ends the game like 「게임 종료」.
QA_MARK = "$1003"
QA_FLAGS = list(range(710, 725)) + [525, 612]  # bit flags the extras/flowchart screens test
QA_COUNTS = [750, 751, 752, 753]               # scene-replay counters (omake_scene)
QA_VIEWS = {v: 903 + i for i, v in enumerate(QA_FLAGS + QA_COUNTS)}   # 710..724 -> 903..917 in order
QA_DLGNO = 14
QA_DLGNO_FRESH = 15     # 「처음 상태로 되돌리기」 on: the reset question (frame 25)
QA_DLGNO_RESTORE = 16   # off: back to the kept records (frame 26)
QA_SCREENS = ["omake_bgm.fes", "omake_cg.fes", "omake_ending.fes", "omake_hscene.fes", "omake_movie.fes",
              "omake_scene.fes", "omake_sysvoice.fes", "conf_flowchart.fes"]
QA_FILES = QA_SCREENS + ["omake_cgview.fes", "title.fes", "conf_dialog.fes", "dialog.fes", "flow.fes"]


_CG_NAMES = []


def _cg_names():
    """CG names in gallery-number order (config.int/cglist.dat; the two editions' lists are equal)"""
    if not _CG_NAMES:
        import cglist
        a = cglist.names(r"Y:\AI\island-steam-ko\gog-orig")
        b = cglist.names(r"Y:\AI\island-steam-ko\steam-orig")
        if a != b or not a or not all(x[:1].isalpha() for x in a):
            raise SystemExit("cglist.dat: the editions differ or a name does not start with a letter")
        _CG_NAMES.extend(a)
    return _CG_NAMES


def _qa_view_section():
    L = ["#QA_VIEW"]
    L += ["$%d = $%d" % (QA_VIEWS[v], v) for v in QA_FLAGS + QA_COUNTS]
    L += ["if (%s==1)" % QA_VAR] + ["$%d = -1" % QA_VIEWS[v] for v in QA_FLAGS] + ["$%d = 999" % QA_VIEWS[v] for v in QA_COUNTS] + ["endif"]
    return L


def _qa_lines(text, fn):
    eol = "\r\n" if "\r\n" in text else "\n"
    return eol, text.split(eol)


def _qa_find(L, line, fn, start=0, stop=None, count=None):
    hits = [i for i in range(start, len(L) if stop is None else stop) if L[i].strip() == line]
    if not hits or (count is not None and len(hits) != count):
        raise SystemExit("%s: line %r found %d times" % (fn, line, len(hits)))
    return hits[0]


def _qa_block(L, label, fn):
    i = _qa_find(L, label, fn, count=1)
    j = i + 1
    while j < len(L) and not L[j].strip().startswith("#"):
        j += 1
    return i, j


def _qa_start(L, fn):
    i = _qa_find(L, "#START", fn, count=1)
    L.insert(i + 1, "call QA_VIEW")
    return 1


def qa_fes(fn, text):
    """-> (text, edits) for the 검수 보기 option; other scripts are returned unchanged"""
    name = fn.lower()
    if name not in QA_FILES:
        return text, 0
    eol, L = _qa_lines(text, name)
    n = 0
    if name in QA_SCREENS:
        rx = re.compile(r"\$(\d+)(?!\d)")
        rx_ix = re.compile(r"\$\((\d+)\+")
        for i, line in enumerate(L):
            if "$814" in line:                  # system-voice choice by story progress: left as is
                continue
            s = line.strip()
            m = re.match(r"\$(\d+)\s*=", s)
            if m and int(m.group(1)) in QA_VIEWS:
                raise SystemExit("%s: writes an unlock flag: %s" % (name, s))
            new = rx.sub(lambda mm: "$%d" % QA_VIEWS[int(mm.group(1))] if int(mm.group(1)) in QA_VIEWS else mm.group(0), line)
            new = rx_ix.sub(lambda mm: "$(%d+" % QA_VIEWS[int(mm.group(1))] if int(mm.group(1)) in QA_VIEWS else mm.group(0), new)
            if new != line:
                L[i] = new
                n += 1
        n += _qa_start(L, name)
        L += _qa_view_section()
    if name in ("omake_cg.fes", "omake_cgview.fes"):
        # CG registration answers: everything registered / nothing registered
        out = []
        for line in L:
            out.append(line)
            s = line.strip()
            m = re.match(r"cgreg_t (\d+) (.+)$", s)
            if m:
                v = m.group(1)
                out += ["if (%s==1)" % QA_VAR, "$%s = 1" % v, "endif", "if (%s==2)" % QA_VAR, "$%s = 0" % v, "endif"]
                n += 1
            m = re.match(r"cgregnum (.+) (\d+)$", s)
            if m:
                e, v = m.group(1), m.group(2)
                out += ["if (%s==1)" % QA_VAR, "cgregmax %s %s" % (e, v), "endif", "if (%s==2)" % QA_VAR, "$%s = 0" % v, "endif"]
                n += 1
        L = out
        if name == "omake_cgview.fes":
            # the viewer pages through `img_cg loadlist2`, which counts registered variants only
            # (exe: it walks the CG's variants and skips unregistered ones). `loadlist` returns the
            # n-th variant as is, but with a CG *number* it evaluates the wrong argument buffer (the
            # last one parsed, "0") - every CG opened as the first one (11-08 user: "뭘 선택해도
            # 첫번째 CG만"). Given a CG *name* it takes its name path, which is right: so while
            # everything is open the viewer calls it by name, one line per CG of cglist.dat.
            k = [i for i, line in enumerate(L) if re.match(r"\s*img_cg loadlist2 ", line)]
            if len(k) != 1:
                raise SystemExit("omake_cgview.fes: 'img_cg loadlist2' found %d times" % len(k))
            line = L[k[0]]
            m = re.match(r"(\s*)img_cg loadlist2 (\S+) \$522 (\S+) (\S+)\s*$", line)
            if not m:
                raise SystemExit("omake_cgview.fes: loadlist2 line not in the expected form")
            pre, a2, var, a5 = m.groups()
            blk = ["if (%s==1)" % QA_VAR]
            for i, cg in enumerate(_cg_names()):
                blk += ["if ($522==%d)" % i, "%simg_cg loadlist %s %s %s %s" % (pre, a2, cg, var, a5), "endif"]
            blk += ["else", line, "endif"]
            L[k[0]:k[0] + 1] = blk
            n += 1 + _qa_start(L, name)
            L += _qa_view_section()
    if name == "title.fes":
        # only the extras button follows the view (the title picture, the new-game start scene and the
        # system voice still follow the real progress); the view is made right before each check because
        # coming back from the settings runs #BTN_SHOW, not #START
        hits = [i for i, line in enumerate(L) if line.strip() == "if ($525==0)"]
        if len(hits) != 3:
            raise SystemExit("title.fes: 'if ($525==0)' found %d times" % len(hits))
        for i in reversed(hits):
            L[i] = L[i].replace("$525", "$%d" % QA_VIEWS[525])
            L.insert(i, "call QA_VIEW")
        n += len(hits)
        L += _qa_view_section()
    if name == "flow.fes":
        i = _qa_find(L, "#GO_LOGO", name, count=1)
        L.insert(i + 1, "%s = 0" % QA_VAR)
        n += 1
    if name == "dialog.fes":
        i, j = _qa_block(L, "#START", name)
        k = _qa_find(L, "btn_check enable 1", name, i, j, count=1)
        L[k + 1:k + 1] = [x for d in (QA_DLGNO, QA_DLGNO_FRESH, QA_DLGNO_RESTORE)
                          for x in ("if ($1027==%d)" % d, "btn_check disp 0", "btn_check enable 0", "endif")]
        n += 1
    if name == "conf_dialog.fes":
        n += _qa_conf_dialog(L, name)
    return eol.join(L), n


def _qa_conf_dialog(L, fn):
    v = QA_VAR
    i = _qa_find(L, "BUTTON btn_check[11]", fn, count=1)
    L[i] = L[i].replace("btn_check[11]", "btn_check[13]")
    i = _qa_find(L, "btn_check[10] sys_dialogconf 210 230 260 280 790 pl_base 0", fn, count=1)
    L[i + 1:i + 1] = ["btn_check[11] sys_dialogconf 211 231 261 281 791 pl_base 0",
                      "btn_check[12] sys_dialogconf 212 232 262 282 792 pl_base 0"]
    i = _qa_find(L, "2 1,4 1,3,0,-1", fn, count=1)
    L[i] = L[i].replace("2 1,4 1,3,0,-1", "2 1,6 1,3,0,-1")
    i = _qa_find(L, "btn_check[10] 2,0,3", fn, count=1)
    L[i + 1:i + 1] = ["btn_check[11] 2,0,4", "btn_check[12] 2,0,5"]
    i = _qa_find(L, "#START2", fn, count=1)
    L.insert(i + 1, "call QA_SHOW")
    # clicks: the two rows before the original row loop (if/else so nothing else runs after a jump)
    i, j = _qa_block(L, "#WAIT_USER", fn)
    k = _qa_find(L, "next SELECT_SWITCH", fn, i, j, count=1)
    if [x.strip() for x in L[k - 2:k + 1]] != ["$814 = 900", "\\3 = 0", "next SELECT_SWITCH"]:
        raise SystemExit("conf_dialog.fes: WAIT_USER row loop not in the expected form")
    L[k - 2:k + 1] = ["if (_CLICK_L_==btn_check[11])", "next QA_CLICK_OPEN", "else",
                      "if (_CLICK_L_==btn_check[12])", "next QA_CLICK_FRESH", "else",
                      "$814 = 900", "\\3 = 0", "next SELECT_SWITCH", "endif", "endif"]
    # focus pictures: the original rows read their switch variable through \(100+@)
    for label, ours in (("#btn_check.FOCUS", ["if (@==11)", "btn_check[11] setid 2", "if (%s==1)" % v, "btn_check[11] setid 3", "endif", "endif",
                                              "if (@==12)", "btn_check[12] setid 2", "if (%s==1)" % QA_MARK, "btn_check[12] setid 3", "endif", "endif"]),
                        ("#btn_check.UNFOCUS", ["if (@>10)", "call QA_SHOW", "endif"])):
        i, j = _qa_block(L, label, fn)
        first = i + 1
        if label == "#btn_check.FOCUS":
            first = _qa_find(L, "call SYSVOICE", fn, i, j) + 1
        L[j:j] = ["endif"] + ours
        L.insert(first, "if (@<11)")
    i = _qa_find(L, "#SET_DEFAULT", fn, count=1)
    L[i + 1:i + 1] = ["%s = 0" % v, "call QA_SHOW"]
    L += ["#QA_SHOW", "btn_check[11] setid 0", "btn_check[12] setid 0",
          "if (%s==1)" % v, "btn_check[11] setid 1", "endif", "if (%s==1)" % QA_MARK, "btn_check[12] setid 1", "endif",
          # `next` jumps within the same frame: back to WAIT_USER without `wait 1` reads the same click
          # again and loops forever (the game froze in the 11-08 test); the original SELECT_SWITCH waits too
          "#QA_CLICK_OPEN", "$814 = 900", "call SYSVOICE",
          "if (%s==1)" % v, "%s = 0" % v, "call QA_SHOW", "wait 1", "next WAIT_USER",
          "else", "call SET_ENABLE_OFF", "$1027 = %d" % QA_DLGNO, "execfes dialog", "next QA_CHECK_OPEN", "endif",
          "#QA_CHECK_OPEN",
          "if (_EXITCODE_==1)", "endfes", "%s = 1" % v, "call SET_ENABLE", "call QA_SHOW", "call SYSVOICE_STOP", "next WAIT_USER", "endif",
          "if (_EXITCODE_==0)", "endfes", "call SET_ENABLE", "call QA_SHOW", "call SYSVOICE_STOP", "next WAIT_USER", "endif",
          # 「처음 상태로 되돌리기」: asks (15 reset / 16 back to the kept records); 예 = the request to the DLL, then the
          # game ends the way 「게임 종료」 does (#CHECK_GAMEQUIT) - the change is made at the next start
          "#QA_CLICK_FRESH", "$814 = 900", "call SYSVOICE", "call SET_ENABLE_OFF",
          "if (%s==1)" % QA_MARK, "$1027 = %d" % QA_DLGNO_RESTORE, "else", "$1027 = %d" % QA_DLGNO_FRESH, "endif",
          "execfes dialog", "next QA_CHECK_FRESH",
          "#QA_CHECK_FRESH",
          "if (_EXITCODE_==1)", "endfes",
          "if (%s==1)" % QA_MARK, "opensite http islandko-restore", "else", "opensite http islandko-reset", "endif",
          "call SYSVOICE_WAIT", "call FADEOUT", "exit 0", "next SLEEP", "endif",
          "if (_EXITCODE_==0)", "endfes", "call SET_ENABLE", "call QA_SHOW", "call SYSVOICE_STOP", "next WAIT_USER", "endif"]
    return 9


# Codex 10-28 system-voice captions for Steam: all 34 screen scripts (Korean UI FES + a caption
# for every system voice). Built on the same Korean UI baseline; never run in the Steam game by Codex.
CAPTION_DIR = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\system-voice-staging\v1\steam\logical"
CAPTION_MAP = r"P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\parallel-ui-20261028\lane5-integration\system-voice-staging\v1\encoding_map.json"


def ui_sources(key, captions=True):
    """Codex Korean UI texts decoded to Unicode (their PUA tables), plus originals."""
    dec, _ = codex_decoder(CODEX_MAP)
    out = {}
    kf_k = cs2.Kif(os.path.join(CODEX_PAYLOAD, "fes.int"), key)
    for n in CODEX_FES:
        data, z = fes_unpack(kf_k.read(n))
        out[("fes", n)] = (dec(data), z)
    if captions and os.path.isdir(CAPTION_DIR):
        cdec, _ = codex_decoder(CAPTION_MAP)
        for n in sorted(os.listdir(CAPTION_DIR)):
            if n.lower().endswith(".fes"):
                data, z = fes_unpack(open(os.path.join(CAPTION_DIR, n), "rb").read())
                txt = caption_fix(cdec(data))[0]
                if n.lower() == "conf_sound.fes":
                    txt = sound_tab_option(txt)[0]
                    txt = decide_caption(txt)[0]
                txt = caption_speakers(txt)[0]
                out[("fes", n)] = (txt, z)
    kc_k = cs2.Kif(os.path.join(CODEX_PAYLOAD, "config.int"), key)
    for n in ["startup.xml", "startup_master.xml"]:
        out[("config", n)] = (dec(kc_k.read(n)), None)
    out[("loose", "config/startup.xml")] = (dec(open(os.path.join(CODEX_PAYLOAD, "config", "startup.xml"), "rb").read()), None)
    return out


def merge_xml(codex_text, orig_text, save_override=None, sticky_override=None):
    """Codex Korean XML with our font and the original save path / sound focus lines.
    Lines are aligned with difflib; only <save>/<sticky> lines Codex changed are put back."""
    a = orig_text.split("\n"); b = codex_text.split("\n")
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    res = []
    restored = 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            res.extend(b[j1:j2])
        elif op == "replace" and (i2 - i1) == (j2 - j1):
            for x, y in zip(a[i1:i2], b[j1:j2]):
                if re.search(r"<(save|sticky)>", x) and not x.strip().startswith("<!--"):
                    res.append(x); restored += 1
                else:
                    res.append(y)
        else:
            res.extend(b[j1:j2])
    t = "\n".join(res)
    n_font = t.count(CODEX_FAMILY)
    t = t.replace(CODEX_FAMILY, FONT_FAMILY)
    # system-voice captions need a wider font texture area: area02 6x3 -> 10x3 blocks of 256 px
    # (Codex's GOG fix; same VRAM layout in the Steam build, no overlap with area00/01)
    t, n_vram = re.subn(r"(<area02>\s*<sx>0</sx>\s*<sy>17</sy>\s*<dx>)6(</dx>)", r"\g<1>10\g<2>", t)
    if save_override is not None:
        t, n = re.subn(r"(?m)^(\s*)<save>[^<]*</save>", lambda m: m.group(1) + "<save>" + save_override + "</save>", t, count=1)
        assert n == 1
    if sticky_override is not None:
        t, n = re.subn(r"<sticky>\d</sticky>", "<sticky>%d</sticky>" % sticky_override, t)
    return t, restored, n_font


# 凛音 and リンネ are both 「린네」 in Korean. User decisions: 11-08 afternoon 「색으로 구분」 (light sky blue), 11-08
# evening (Switch port, seen on screen) emphasis dots instead - 「점을 글자 바로 위에」, 「큰 쪽」 - one round dot centred over
# each letter of the リンネ side's 「린네」; name labels unmarked (Switch: ruby would spread the label), 「린네」 inside an
# existing ruby group unmarked (rubies do not nest), hiragana and kanji-with-katakana-ruby lines unmarked.
# PC engine (GOG copy 11-08): ruby works in the message, novel and full windows and the backlog (size 10 px, centred
# over its base) -> each dotted letter is a ruby group [린/•][네/•], • = kocodec.RINNE_DOT, a 0.70 em round dot in the
# patch font (build_font.py): 7 px across, 2 px over the letter at the 26 px text, ~0.27 of it like the Switch port.
# The save/load panel strips rubies (plain 「린네」). CHOICES CANNOT TAKE A RUBY: any [base/ruby] in an option crashes the
# engine (access violation; tried with a ruby size, a top margin and `layout font` in select.fes - the option strings
# are 30 px VRAM rows), and a glyph or userfont image reaching above its cell is squeezed into the cell. So the three
# choice options keep the afternoon's light sky blue: two otherwise unused kanji codes EA9F EAA0 (kocodec.RINNE_ALIAS)
# that select.fes / novelselect.fes map to userfont frames 20, 21 (#a0c8e8, the user's pick on the PC choice screen;
# work\img-ko\manifest_rinne.json, tools\make_rinne_frames.py) and the patch font draws as plain 「린」「네」 anywhere else.
# The engine scales a userfont canvas (32x32) to the text size and adds its own outline + shadow, so the frames are the
# glyph fill only (drawn at 32 px).
# Which 「린네」: the parent's table (rinne_color_indices.json: lines with both 凛音 and リンネ, lines with neither
# form, 0-based occurrence lists) first; otherwise text lines whose original uses リンネ only (no 凛音, no
# hiragana りんね) -> every 「린네」, choice options naming リンネ. (Name labels whose original is リンネ are planned
# but get no mark.)
RINNE_MARK = "".join(RINNE_ALIAS)          # choices: 「린」「네」 on the unused kanji codes EA9F EAA0 (userfont colour)
RINNE_DOTTED = "[린/%s][네/%s]" % (RINNE_DOT, RINNE_DOT)   # text: a ruby dot over each letter
RINNE_TABLE = r"F:\AI\island-gemini\review\work\rinne_color_indices.json"
RINNE_FRAMES = {"choice": (20, 21)}


def rinne_plan(entries):
    """({kit id: [0-based occurrences of 「린네」 in its Korean to mark]}, counts)"""
    raw = json.load(open(RINNE_TABLE, encoding="utf-8"))
    table = {k.split("::", 1)[1]: v for k, v in raw.items()}
    plan, st = {}, Counter()
    for e in entries:
        ko, src, typ = e["ko"] or "", e["source_raw"], e["line_type"]
        n = ko.count("린네")
        if e["id"] in table:
            idx = sorted(set(table[e["id"]]))
            if any(i >= n for i in idx):
                raise SystemExit("rinne table: %s lists occurrence %s of %d" % (e["id"], idx, n))
            st["table_lines"] += 1
            if idx:
                plan[e["id"]] = idx
                st["table_marked_lines"] += 1
            continue
        if typ == 32 and "リンネ" in src and "凛音" not in src and "りんね" not in src:
            kind = "text"
        elif typ == 33 and src == "リンネ":
            kind = "name"
        elif typ == 48 and "リンネ" in src and "凛音" not in src:
            kind = "choice"
        else:
            continue
        if not n:
            st[kind + "_without_korean_name"] += 1
            continue
        plan[e["id"]] = list(range(n))
        st[kind + "_lines"] += 1
    st["table_entries_not_in_pc_kit"] = sum(1 for k in table if k not in {e["id"] for e in entries})
    return plan, st


def rinne_apply(ko, idx, line_type):
    """mark the listed occurrences of 「린네」: text lines -> RINNE_DOTTED (an occurrence inside a ruby group stays plain),
    choice options -> RINNE_MARK, name labels -> unchanged. -> (ko, marked, left_in_ruby)"""
    if line_type == 33:
        return ko, 0, 0
    spans = [(m.start(), m.end()) for m in RUBY.finditer(ko)] if line_type == 32 else []
    out, pos, k, want, marked, in_ruby = [], 0, 0, set(idx), 0, 0
    while True:
        j = ko.find("린네", pos)
        if j < 0:
            break
        out.append(ko[pos:j])
        if k in want and any(a <= j < b for a, b in spans):
            out.append("린네")
            in_ruby += 1
        elif k in want:
            out.append(RINNE_DOTTED if line_type == 32 else RINNE_MARK)
            marked += 1
        else:
            out.append("린네")
        pos, k = j + 2, k + 1
    out.append(ko[pos:])
    if want and max(want) >= k:
        raise SystemExit("rinne: occurrence %d of %d" % (max(want), k))
    return "".join(out), marked, in_ruby


RINNE_FES = ["select.fes", "novelselect.fes"]


def rinne_fes(name, text):
    """the choice screens: userfont map lines for the colour codes (frames 20, 21), added after the script's own ⑨
    line; existing lines untouched. -> (text, lines added); other scripts unchanged."""
    n = name.lower()
    if n not in RINNE_FES:
        return text, 0
    L = text.split("\n")
    cr = "\r" if L and L[0].endswith("\r") else ""
    codes = ["%02X%02X" % tuple(k.encode("cp932")) for k in RINNE_ALIAS]
    hits = [i for i, s in enumerate(L) if s.strip() == "str userfont 0x8748 9"]
    if len(hits) != 1:
        raise SystemExit("%s: the ⑨ userfont line found %d times" % (name, len(hits)))
    new = ["str userfont 0x%s %d" % (c, f) for c, f in zip(codes, RINNE_FRAMES["choice"])]
    L[hits[0] + 1:hits[0] + 1] = [s + cr for s in new]
    return "\n".join(L), len(new)


# 11-08 (found on the GOG test copy): a choice line is "<n> <target> <text>" and the engine takes the text only up
# to the first half-width space - the Japanese never has one, the English release wraps every choice text as
# "(:...)" (116 of 116). 75 of our 116 Korean choice texts have spaces and showed their first word only.
# GOG: wrapped like the English release. Steam (Japanese engine, 2.6.1.68): nothing in its scripts uses "(:" and
# the game may not be run for a test, so its spaces become full-width spaces (U+3000, one DBCS character the
# tokenizer cannot split) and its ASCII brackets full-width ones (an unwrapped "(" also ended the text on the GOG
# engine) - this form checked to display whole on the GOG engine.
def choice_text(ko, edition):
    if edition == "gog":
        return "(:" + ko + ")"
    return ko.replace(" ", "　").replace("(", "（").replace(")", "）")


# 11-09 (user 「첫 선택지에서 린네,린네는 괄호치고 일본어 표기를 해두자」): the first choice (com01_selB) offers 凛音 and
# リンネ, both 「린네」 in Korean - each option gets its Japanese spelling in brackets: 「린네(凛音)」「린네(リンネ)」.
# 凛 音 リ ン ネ are original-game characters (never donor codes) that the patch font (Noto Sans CJK JP) draws as they
# are. Added after rinne_apply (the リンネ option keeps its light-blue 「린네」) and before choice_text (full-width
# brackets on Steam, the "(:...)" wrap on GOG, where brackets inside it show). The kit text is not changed.
CHOICE_JP_NOTE = {"scene.int::com01_selB.cst::line_00003": "凛音", "scene.int::com01_selB.cst::line_00004": "リンネ"}


def choice_note(e, ko):
    """-> (ko, 1 if the Japanese spelling was added)"""
    note = CHOICE_JP_NOTE.get(e["id"])
    if note is None:
        return ko, 0
    if e["source_raw"] != note or e["ko"] != "린네":
        raise SystemExit("choice note: %s no longer reads %s / 린네" % (e["id"], note))
    return ko + "(" + note + ")", 1


# 11-09 (user 「고쳐」 to: in the settings screens the menu-voice caption covers the lower half of the tab row): Codex's
# caption box is x 48..1232 drawn at y 644 and its band (자막 배경) x 32..1248, y 624..696, while the settings tab
# screens (conf_*.fes) have the tab row down to y 668 and the 돌아가기/타이틀/게임 종료 buttons from x 1040 (GOG copy
# capture). There the caption goes under the tabs and left of the buttons: box x 40..1024 (984 wide, centred in it)
# drawn at y 680, band x 32..1032, y 670..720. The widest caption string of these screens is 868 px at the 28 px size
# (both builds), so nothing wraps. Every other screen keeps Codex's place.
CAP_PLACE = [("ko_cap_bg 32,624 0,0 1216,72 ", "ko_cap_bg 32,670 0,0 1000,50 "),
             ("ko_cap_text 1280,5000 1184,68 48,628 ", "ko_cap_text 1280,5000 984,68 40,680 ")]
CAP_POS = ("ko_cap_text pos 48 644", "ko_cap_text pos 40 680")


def caption_place(name, text):
    """settings tab screens only -> (text, caption draws moved)"""
    if not name.lower().startswith("conf_") or "ko_cap_text" not in text:
        return text, 0
    for a, b in CAP_PLACE:
        if text.count(a) != 1:
            raise SystemExit("%s: caption object line %r found %d times" % (name, a.strip(), text.count(a)))
        text = text.replace(a, b)
    n = text.count(CAP_POS[0])
    text = text.replace(CAP_POS[0], CAP_POS[1])
    other = set(re.findall(r"ko_cap_text pos [^\r\n]*", text)) - {CAP_POS[1]}
    if not n or other:
        raise SystemExit("%s: caption draws moved %d, other caption places %s" % (name, n, sorted(other)))
    return text, n


DOTS = set("・･.…")

# 11-08 night (Switch port, user 「좁은 점으로」 after seeing 「・」 and 「･」 on screen): every middle dot of the Korean
# script - the Latin 「·」 U+00B7 (on a donor code here) and the full-width 「・」 U+30FB, inline or as an emphasis-dot
# ruby - becomes the narrow 「･」 U+FF65 (CP932 A5, a half-width cell), like the Switch build's narrow_dots. Done
# before word wrapping (the line gets shorter by one cell per dot).
NARROW_DOT = "･"


def narrow_dots(ko):
    """-> (ko, dots changed)"""
    if not ko:
        return ko, 0
    n = ko.count("·") + ko.count("・")
    return (ko.replace("·", NARROW_DOT).replace("・", NARROW_DOT), n) if n else (ko, 0)


def normalize_ko(ko):
    """Engine-side formatting only (translation text is untouched):
    emphasis dots put on a blank, e.g. [ /・], become the bare blank."""
    n = 0

    def fix(m):
        nonlocal n
        base, _, ruby = m.group(1).partition("/")
        if not base.strip() and ruby and set(ruby) <= DOTS:
            n += 1
            return base
        return m.group(0)

    return RUBY.sub(fix, ko), n


def check_entry(e, ko):
    """Machine checks on one translated entry. Returns list of problem tags."""
    p = []
    src = e["source_raw"]
    if e["line_type"] == 48 and e.get("blank_choice"):
        return p
    if CODE.findall(src) != CODE.findall(ko):
        p.append("code_sequence")
    stray = CODE.sub("", ko)
    if "\\" in stray:
        p.append("stray_backslash")
    for m in RUBY.finditer(ko):
        if m.group(1).count("/") != 1 or not all(x.strip() for x in m.group(1).split("/")):
            p.append("ruby_shape")
    if ko.count("[") != ko.count("]"):
        p.append("bracket_balance")
    if JPCHARS.search(ko):
        p.append("japanese_left")
    if src.strip() and not ko.strip():
        p.append("empty")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=r"Y:\AI\island-steam-ko\build\ko")
    ap.add_argument("--test-save", default=None, help="save folder for a test copy (else original)")
    ap.add_argument("--test-sticky", type=int, default=None)
    ap.add_argument("--no-scene", action="store_true")
    ap.add_argument("--no-wrap", action="store_true", help="leave line breaking to the engine")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)
    key = cs2.crc_key(cs2.passphrase(os.path.join(ORIG, "ISLAND.exe")))

    entries, kstats = kit.load()
    ui = ui_sources(key)
    chars = set()
    for e in entries:
        if e["ko"]:
            chars.update(e["ko"])
    for (kind, name), (text, _) in ui.items():
        chars.update(text)
    import usedchars
    exclude = usedchars.original_chars()
    prior = None
    if os.path.exists(PUA_TABLE) and "donor-v2" in open(PUA_TABLE, encoding="utf-8").read(200):
        prior = {c: list(b) for c, b in Codec.load(PUA_TABLE).enc.items()}
        clash = [c for c, b in prior.items() if bytes(b).decode("cp932") in exclude | chars]
        if clash:
            raise SystemExit("donor table clashes with game text: %d" % len(clash))
    codec = Codec.build(chars, prior, exclude)
    codec.save(PUA_TABLE)

    report = {"kit": kstats, "pua_assigned": len(codec.enc), "problems": Counter(), "problem_ids": defaultdict(list)}

    # ---------- scene.int ----------
    if not args.no_scene:
        by_file = defaultdict(list)
        for e in entries:
            by_file[e["file"]].append(e)
        rinne, rinne_st = rinne_plan(entries)
        rinne_done = Counter()
        notes_added = 0
        src_kif = cs2.Kif(os.path.join(ORIG, "scene.int"), key)
        repl = {}
        names = defaultdict(Counter)
        fallback = 0
        wrap_breaks = 0
        replaced = Counter()
        with open(src_kif.path, "rb") as fh:
            for fname, rows in sorted(by_file.items()):
                blob = src_kif.read(fname, fh)
                lines, meta = cs2.parse_cst(blob)
                for e in rows:
                    typ, raw = lines[e["index"]]
                    assert typ == e["line_type"], (fname, e["index"])
                    ko = e["ko"]
                    if ko is None:
                        report["problems"]["missing"] += 1
                        report["problem_ids"]["missing"].append(e["id"])
                        fallback += 1
                        continue
                    ko, ndot = narrow_dots(ko)
                    report["problems"]["narrowed_middle_dots"] += ndot
                    ko, nfix = normalize_ko(ko)
                    if nfix:
                        report["problems"]["fixed_dot_on_blank"] += nfix
                        report["problem_ids"]["fixed_dot_on_blank"].append(e["id"])
                    for tag in check_entry(e, ko):
                        report["problems"][tag] += 1
                        report["problem_ids"][tag].append(e["id"])
                    if e["line_type"] == 32 and not args.no_wrap:
                        # the engine wraps by character cells (58 units, measured in game);
                        # break at spaces instead so Korean words are never split
                        ko, nbr = wrapsim.word_wrap(ko, 58, 1)
                        wrap_breaks += nbr
                    if e["line_type"] == 33:
                        names[e["source_raw"]][ko] += 1
                    if e["id"] in rinne:
                        before = ko.count("린네")
                        ko, marked, in_ruby = rinne_apply(ko, rinne[e["id"]], e["line_type"])
                        if before != e["ko"].count("린네"):
                            raise SystemExit("rinne: formatting changed the 「린네」 count in " + e["id"])
                        rinne_done["planned_%d" % e["line_type"]] += 1
                        rinne_done["lines_%d" % e["line_type"]] += bool(marked)
                        rinne_done["pairs_%d" % e["line_type"]] += marked
                        rinne_done["left_in_ruby"] += in_ruby
                    if e["line_type"] == 48 and not e.get("blank_choice"):
                        ko, nn = choice_note(e, ko)
                        notes_added += nn
                        ko = choice_text(ko, "steam")
                    e["ko_built"] = ko
                    if e["line_type"] == 48:
                        cmd = raw.decode("cp932")
                        pre, suf = e["command_prefix"], e["command_suffix"]
                        if pre + e["source_raw"] + suf != cmd:
                            raise SystemExit("choice command mismatch " + e["id"])
                        if e.get("blank_choice"):
                            ko = e["source_raw"]
                        new = pre + ko + suf
                    else:
                        new = ko
                    lines[e["index"]] = (typ, codec.encode(new))
                    replaced[e["line_type"]] += 1
                repl[fname] = cs2.build_cst(lines, meta)
                # round trip: decode back equals what we meant
                l2, _ = cs2.parse_cst(repl[fname])
                assert len(l2) == len(lines)
        out_scene = os.path.join(args.out, "scene.int")
        src_kif.write(out_scene, repl)
        # verify by reading back every replaced line
        chk = cs2.Kif(out_scene, key)
        bad = 0
        with open(out_scene, "rb") as fh:
            for fname, rows in by_file.items():
                lines, _ = cs2.parse_cst(chk.read(fname, fh))
                for e in rows:
                    if e["ko"] is None:
                        continue
                    t = codec.decode(lines[e["index"]][1])
                    kb = e.get("ko_built", e["ko"])
                    want = (e["command_prefix"] + (e["source_raw"] if e.get("blank_choice") else kb) + e["command_suffix"]) if e["line_type"] == 48 else kb
                    bad += t != want
        if sum(rinne_done["planned_%d" % t] for t in (32, 33, 48)) != len(rinne):
            raise SystemExit("rinne: %d planned lines seen of %d" % (sum(rinne_done["planned_%d" % t] for t in (32, 33, 48)), len(rinne)))
        if notes_added != len(CHOICE_JP_NOTE):
            raise SystemExit("choice note: %d of %d options got their Japanese spelling" % (notes_added, len(CHOICE_JP_NOTE)))
        report["scene"] = {"files": len(repl), "replaced_by_type": dict(replaced), "readback_mismatch": bad, "word_wrap_breaks": wrap_breaks,
                           "untranslated_fallback": fallback, "bytes": os.path.getsize(out_scene), "choice_japanese_notes": notes_added,
                           "rinne": {"dotted_text_lines": rinne_done["lines_32"], "dotted_pairs": rinne_done["pairs_32"],
                                     "left_in_ruby": rinne_done["left_in_ruby"], "coloured_choice_options": rinne_done["lines_48"],
                                     "name_labels_unmarked": rinne_done["planned_33"], "plan": dict(rinne_st)}}
        multi = {jp: dict(c) for jp, c in names.items() if len(c) > 1}
        report["name_variants"] = {"japanese_names": len(names), "with_several_korean_forms": len(multi)}
        json.dump({jp: c for jp, c in multi.items()}, open(os.path.join(DATA, "name_variants.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- fes.int ----------
    fk = cs2.Kif(os.path.join(ORIG, "fes.int"), key)
    frepl = {}
    qa_edits = {}
    rinne_fes_edits = {}
    cap_moved = {}
    for (kind, n), (text, z) in sorted(ui.items()):
        if kind == "fes":
            text, cm = caption_place(n, text)
            if cm:
                cap_moved[n] = cm
            text, q = qa_fes(n, text)
            if q:
                qa_edits[n] = q
            text, r = rinne_fes(n, text)
            if r:
                rinne_fes_edits[n] = r
            frepl[n] = fes_pack(codec.encode(text), z)
    have = {k.lower() for k in frepl}
    for e in fk.entries:                      # 검수 보기 / 린네 colour scripts Codex did not touch (omake_cgview.fes, log_01.fes)
        low = e["name"].lower()
        if (low in QA_FILES or low in RINNE_FES) and low not in have:
            data, z = fes_unpack(fk.read(e["name"]))
            text, q = qa_fes(e["name"], data.decode("cp932"))
            if low in QA_FILES:
                qa_edits[e["name"]] = q
            text, r = rinne_fes(e["name"], text)
            if r:
                rinne_fes_edits[e["name"]] = r
            frepl[e["name"]] = fes_pack(text.encode("cp932"), z)
    missing = [n for n in QA_FILES if n not in {k.lower() for k in qa_edits}]
    if missing:
        raise SystemExit("검수 보기: scripts not edited: %s" % missing)
    missing = [n for n in RINNE_FES if n not in {k.lower() for k in rinne_fes_edits}]
    if missing:
        raise SystemExit("린네 colour: scripts not edited: %s" % missing)
    missing = [n for (kind, n), (text, z) in ui.items() if kind == "fes" and n.lower().startswith("conf_") and "ko_cap_text" in text and n not in cap_moved]
    if missing:
        raise SystemExit("settings caption place: scripts not edited: %s" % missing)
    fk.write(os.path.join(args.out, "fes.int"), frepl)
    captions_on = any(k == ("fes", "title.fes") for k in ui)

    # ---------- config.int + loose startup.xml ----------
    ck = cs2.Kif(os.path.join(ORIG, "config.int"), key)
    crepl = {}
    restored_total = 0
    for n in ["startup.xml", "startup_master.xml"]:
        orig_text = ck.read(n).decode("cp932")
        t, restored, nf = merge_xml(ui[("config", n)][0], orig_text, args.test_save, args.test_sticky)
        restored_total += restored
        crepl[n] = codec.encode(t)
    ck.write(os.path.join(args.out, "config.int"), crepl)
    orig_loose = open(os.path.join(ORIG, "config", "startup.xml"), "rb").read().decode("cp932")
    t, restored, nf = merge_xml(ui[("loose", "config/startup.xml")][0], orig_loose, args.test_save, args.test_sticky)
    restored_total += restored
    os.makedirs(os.path.join(args.out, "config"), exist_ok=True)
    with open(os.path.join(args.out, "config", "startup.xml"), "wb") as f:
        f.write(codec.encode(t))
    report["ui"] = {"fes_replaced": len(frepl), "config_replaced": len(crepl), "save_or_sticky_lines_restored": restored_total,
                    "font_family": FONT_FAMILY, "qa_view_edits": qa_edits, "rinne_fes_edits": rinne_fes_edits,
                    "settings_caption_draws_moved": cap_moved}

    report["problems"] = dict(report["problems"])
    ids = dict(report.pop("problem_ids"))
    json.dump({"report": report, "problem_ids": ids}, open(os.path.join(args.out, "..", "text_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
