"""Steam (JP) vs GOG: the differing images (image.int) and movies (movie.int) - same picture with other text, or other
content? Images: frames, sizes, and how much of each frame's pixels differ (share, bounding box). Movies: format,
length, picture size, audio identical?, and picture similarity (PSNR) over time. Numbers and name prefixes only."""
import collections
import hashlib
import io
import json
import os
import re
import subprocess
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, r'P:\AI\island-steam-ko\tools')
import cs2  # noqa: E402
import hg3  # noqa: E402

S = r'Y:\AI\island-steam-ko\steam-orig'
G = r'Y:\AI\island-steam-ko\gog-orig'
TMP = r'Y:\AI\claude-work\island-vercheck'
FF = r'P:\AI\Codex\projects\migrated-from-c\onedrive-chatgpt\아일랜드\switch-native-port\tools\ffmpeg-8.1.2\ffmpeg.exe'
FP = FF.replace('ffmpeg.exe', 'ffprobe.exe')
os.makedirs(TMP, exist_ok=True)
D = json.load(open(r'Y:\AI\island-steam-ko\gog-work\asset_diff.json', encoding='utf-8'))


def open_kif(path, key):
    plain = open(path, 'rb').read(19)[8:19] != b'__key__.dat'
    return cs2.PlainKif(path) if plain else cs2.Kif(path, key)


ks = cs2.crc_key(cs2.passphrase(os.path.join(S, 'ISLAND.exe')))
kg = cs2.crc_key(cs2.passphrase(os.path.join(G, 'ISLAND.exe')))
name = lambda x: x[0] if isinstance(x, (list, tuple)) else (x['name'] if isinstance(x, dict) else x)  # noqa: E731
prefix = lambda n: (re.match(r'[a-z]+_?[a-z]*', n.lower()) or re.match(r'.', n)).group()[:10]  # noqa: E731

# ---- images
a = open_kif(os.path.join(S, 'image.int'), ks)
b = open_kif(os.path.join(G, 'image.int'), kg)
rows = []
for x in D['image.int']['differ']:
    n = name(x)
    ba, bb = a.read(n), b.read(n)
    try:
        fa, fb = hg3.frames(ba), hg3.frames(bb)
    except Exception as ex:
        rows.append((prefix(n), 'unreadable', type(ex).__name__))
        continue
    if len(fa) != len(fb):
        rows.append((prefix(n), 'frame count %d -> %d' % (len(fa), len(fb)), None))
        continue
    worst = 0.0
    kinds = set()
    for f1, f2 in zip(fa, fb):
        if (f1['width'], f1['height']) != (f2['width'], f2['height']):
            kinds.add('size differs')
            continue
        try:
            p1 = np.asarray(hg3.decode(ba, f1).convert('RGBA'), dtype=np.int16)
            p2 = np.asarray(hg3.decode(bb, f2).convert('RGBA'), dtype=np.int16)
        except Exception as ex:
            kinds.add('decode ' + type(ex).__name__)
            continue
        d = np.abs(p1 - p2).max(axis=2) > 8
        share = d.mean()
        if share == 0:
            kinds.add('same pixels')
        else:
            ys, xs = np.nonzero(d)
            box = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1) / d.size
            kinds.add('differs')
            worst = max(worst, share)
            rows.append((prefix(n), 'frame', round(float(share) * 100, 1), round(float(box) * 100, 1)))
    rows.append((prefix(n), 'image', '+'.join(sorted(kinds)), round(worst * 100, 1)))
img = [r for r in rows if r[1] == 'image']
print('== images that differ: %d (+ %d only in GOG)' % (len(D['image.int']['differ']), len(D['image.int']['only_gog'])))
print('by kind:', collections.Counter(r[2] for r in img))
print('by name prefix:', collections.Counter(r[0] for r in img))
fr = [r for r in rows if r[1] == 'frame']
if fr:
    print('differing frames: %d; changed pixels per frame (%%): median %.1f, max %.1f; their bounding box (%% of frame): median %.1f, max %.1f' % (
        len(fr), float(np.median([r[2] for r in fr])), max(r[2] for r in fr), float(np.median([r[3] for r in fr])), max(r[3] for r in fr)))
    print('frames with more than 40%% of pixels changed: %d' % sum(1 for r in fr if r[2] > 40))
other = [r for r in rows if r[1] not in ('image', 'frame')]
print('other image rows:', collections.Counter((r[0], r[1]) for r in other))

# ---- movies
a = open_kif(os.path.join(S, 'movie.int'), ks)
b = open_kif(os.path.join(G, 'movie.int'), kg)


def probe(p):
    out = subprocess.run([FP, '-v', 'error', '-show_entries', 'format=format_name,duration:stream=codec_type,codec_name,width,height,r_frame_rate',
                          '-of', 'json', p], capture_output=True, text=True).stdout
    return json.loads(out or '{}')


def audio_md5(p):
    r = subprocess.run([FF, '-v', 'error', '-i', p, '-map', '0:a:0', '-f', 'md5', '-'], capture_output=True, text=True)
    return r.stdout.strip()[-12:] or None


print('== movies that differ: %d' % len(D['movie.int']['differ']))
for i, x in enumerate(D['movie.int']['differ']):
    n = name(x)
    pa, pb = os.path.join(TMP, 's_%d%s' % (i, os.path.splitext(n)[1])), os.path.join(TMP, 'g_%d%s' % (i, os.path.splitext(n)[1]))
    open(pa, 'wb').write(a.read(n))
    open(pb, 'wb').write(b.read(n))
    qa, qb = probe(pa), probe(pb)

    def desc(q):
        f = q.get('format', {})
        v = [s for s in q.get('streams', []) if s.get('codec_type') == 'video']
        au = [s for s in q.get('streams', []) if s.get('codec_type') == 'audio']
        return '%s %.1fs %s %sx%s %s | audio %s' % (f.get('format_name'), float(f.get('duration', 0) or 0), v[0].get('codec_name') if v else '-',
                                                v[0].get('width') if v else '-', v[0].get('height') if v else '-', v[0].get('r_frame_rate') if v else '-',
                                                au[0].get('codec_name') if au else '-')
    ma, mb = audio_md5(pa), audio_md5(pb)
    # picture similarity: scale GOG to the Steam size, PSNR per frame
    va = [s for s in qa.get('streams', []) if s.get('codec_type') == 'video']
    psnr = None
    if va:
        w, h = va[0]['width'], va[0]['height']
        r = subprocess.run([FF, '-v', 'error', '-i', pa, '-i', pb, '-lavfi',
                            '[1:v]scale=%d:%d,format=yuv420p[g];[0:v]format=yuv420p[s];[s][g]psnr=stats_file=%s' % (w, h, os.path.join(TMP, 'psnr_%d.log' % i).replace('\\', '/').replace(':', '\\:')),
                            '-f', 'null', '-'], capture_output=True, text=True)
        vals = []
        lp = os.path.join(TMP, 'psnr_%d.log' % i)
        if os.path.exists(lp):
            for line in open(lp, encoding='ascii', errors='replace'):
                m = re.search(r'psnr_avg:(\S+)', line)
                if m:
                    vals.append(float('inf') if m.group(1) == 'inf' else float(m.group(1)))
        if vals:
            v = np.array([min(x, 99) for x in vals])
            psnr = 'frames %d, PSNR median %.1f dB, frames under 30 dB %.1f%%, under 20 dB %.1f%%' % (len(v), float(np.median(v)), 100 * float((v < 30).mean()), 100 * float((v < 20).mean()))
    print('movie %d (%s): steam %s' % (i, prefix(n), desc(qa)))
    print('          gog   %s' % desc(qb))
    print('          audio identical: %s | picture: %s' % (ma == mb and ma is not None, psnr))
