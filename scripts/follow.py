"""Follow one person through the same trip in two scenarios, side by side, with a timer.

  python scripts/follow.py baseline proposal_151126

Uses the full-hour recording made by `clip.py ... --hour` (out/clips/<scenario>/fcd_hour.xml and tripinfo_hour.xml).
Both scenarios carry the same people on the same trips, so each person can be followed in both. Picks trips across
Hosur Road and Sarjapura Road near junction C: one typical St John's bus passenger on each road (time saved closest to
the median), and one person who cannot use stairs. Writes report/<second scenario>/follow_<n>.mp4, still_follow_<n>.png
and follow.json (who, from where, how long in each scenario).
"""
import csv, json, math, os, shutil, statistics as st, sys, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from common import P, cfg, JUNCTIONS, run, SIDE_NAME
import imagery as PF

def font(size, bold=False):
    try: return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size)
    except OSError: return ImageFont.load_default()

C = cfg()
A, B = sys.argv[1], sys.argv[2]
OUT = P('report', B); TMP = P('out', 'clips')
LABEL = {'baseline': 'Today', **{k: v.get('label', k) for k, v in C['proposals'].items() if not k.startswith('_')}}
FONT, SMALL, BIG = font(19, True), font(14), font(26, True)
meta = {r['id']: r for r in csv.DictReader(open(P('demand', 'person_meta.csv')))}

def trips(scn):
    out = {}
    for pi in ET.parse(os.path.join(TMP, scn, 'tripinfo_hour.xml')).getroot().findall('personinfo'):
        w = pi.findall('walk')
        if w and all(float(x.get('arrival', -1)) >= 0 for x in w):
            out[pi.get('id')] = dict(depart=float(pi.get('depart')), arrival=max(float(x.get('arrival')) for x in w),
                                     length=sum(float(x.get('routeLength')) for x in w), type=pi.get('type'))
    return out

def tracks(scn, ids):
    out = {i: [] for i in ids}
    for ev, el in ET.iterparse(os.path.join(TMP, scn, 'fcd_hour.xml'), events=('start', 'end')):
        if ev == 'start' and el.tag == 'timestep': t = float(el.get('time'))
        elif ev == 'end' and el.tag == 'person' and el.get('id') in out:
            out[el.get('id')].append((t, float(el.get('x')), float(el.get('y')), float(el.get('speed') or 0)))
        elif ev == 'end' and el.tag == 'timestep': el.clear()
    return out

TA, TB = trips(A), trips(B)
from common import hhmm
W0, W1 = hhmm(C['time']['metrics_begin']), hhmm(C['time']['metrics_end'])     # the recorded hour
both = [i for i in TA if i in TB and i in meta and meta[i]['kind'] == 'crossing' and meta[i]['side'] in ('BC', 'CA')
        and TA[i]['depart'] >= W0 + 4 and max(TA[i]['arrival'], TB[i]['arrival']) <= W1 - 4]
# choose: a St John's bus passenger crossing Hosur Road, one crossing Sarjapura Road, one who cannot use stairs
def typical(pool):
    pool = [i for i in pool if TA[i]['arrival'] - TA[i]['depart'] > 60]
    if not pool: return None
    save = {i: (TA[i]['arrival'] - TA[i]['depart']) - (TB[i]['arrival'] - TB[i]['depart']) for i in pool}
    pos = [i for i in pool if save[i] > 0] or pool
    med = st.median(save[i] for i in pos)
    return min(pos, key=lambda i: abs(save[i] - med))
picks = []
for side in ('BC', 'CA'):
    p = typical([i for i in both if meta[i]['side'] == side and 'St Johns' in meta[i]['place'] and TA[i]['type'] != 'walker_stepfree'])
    if p: picks.append((p, f"Bus passenger at St John's Hospital stop, crossing {SIDE_NAME[side]}"))
p = typical([i for i in both if TA[i]['type'] == 'walker_stepfree' and i not in [x for x, _ in picks]])
if p: picks.append((p, f"Person who cannot use stairs, crossing {SIDE_NAME[meta[p]['side']]} from {meta[p]['place']}"))
tr = {A: tracks(A, [x for x, _ in picks]), B: tracks(B, [x for x, _ in picks])}

def mmss(s): return f"{int(s // 60)}:{int(s % 60):02d}"
summary = []
for n, (pid, what) in enumerate(picks, 1):
    ta, tb = tr[A][pid], tr[B][pid]
    lons = [p[1] for p in ta + tb]; lats = [p[2] for p in ta + tb]
    cx, cy = (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2
    k = math.cos(math.radians(cy))
    half = max((max(lons) - min(lons)) * k, (max(lats) - min(lats)), 0.0016) / 2 + 0.0003      # degrees of latitude
    box = (cx - half / k, cy - half * 0.8, cx + half / k, cy + half * 0.8)
    W = 640; H = int(W * 0.8)
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100); ax = fig.add_axes([0, 0, 1, 1]); PF.basemap(ax, *box, 19); ax.axis('off')
    f = os.path.join(TMP, f'follow_bg_{n}.png'); fig.savefig(f, dpi=100); plt.close(fig)
    bg = ImageEnhance.Brightness(Image.open(f).convert('L').convert('RGB').resize((W, H))).enhance(0.55)
    proj = lambda lon, lat: ((lon - box[0]) / (box[2] - box[0]) * W, (box[3] - lat) / (box[3] - box[1]) * H)
    dep = TA[pid]['depart']; endA, endB = TA[pid]['arrival'], TB[pid]['arrival']
    step = min(b[0] - a[0] for a, b in zip(ta, ta[1:])) if len(ta) > 1 else 2.0
    times = [dep + k * step for k in range(int((max(endA, endB) + 6 - dep) / step) + 1)]   # run on past both arrivals
    fdir = os.path.join(TMP, f'frames_follow_{n}'); shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
    def frame(track, end, title, t, col):
        im = bg.copy(); d = ImageDraw.Draw(im, 'RGBA')
        full = [proj(p[1], p[2]) for p in track]
        if len(full) > 1: d.line(full, fill=col + (70,), width=3)                     # the whole route, faint
        done = [proj(p[1], p[2]) for p in track if p[0] <= t]
        if len(done) > 1: d.line(done, fill=col + (255,), width=5)
        if done:
            x, y = done[-1]
            d.ellipse([x - 10, y - 10, x + 10, y + 10], outline=(255, 255, 255, 255), width=3); d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=col + (255,))
        waiting = any(abs(p[0] - t) < 1 and p[3] < 0.1 for p in track) and t < end
        d.rectangle([0, 0, W, 34], fill=(0, 0, 0, 170)); d.text((10, 7), title, fill='white', font=FONT)
        el = min(t, end) - dep
        msg = f"arrived after {mmss(end - dep)}" if t >= end else f"walking {mmss(el)}" + ("  ·  waiting" if waiting else "")
        d.rectangle([0, H - 44, W, H], fill=(0, 0, 0, 170)); d.text((12, H - 38), msg, fill=(255, 212, 59) if t >= end else 'white', font=BIG)
        return im
    for i, t in enumerate(times):
        a = frame(ta, endA, LABEL[A], t, (240, 101, 255)); b = frame(tb, endB, LABEL[B], t, (240, 101, 255))
        fr = Image.new('RGB', (2 * W + 10, H + 34), (20, 20, 20)); fr.paste(a, (0, 0)); fr.paste(b, (W + 10, 0))
        ImageDraw.Draw(fr).text((10, H + 9), f"{what}.  Same person, same trip, same moment.  Simulation; {round(step * 10)}x speed.",
                                fill=(210, 210, 210), font=SMALL)
        fr.save(os.path.join(fdir, f'{i:05d}.png'))
        if i == len(times) - 1: fr.save(os.path.join(OUT, f'still_follow_{n}.png'))
    run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '10', '-i', os.path.join(fdir, '%05d.png'), '-vf', 'tpad=stop_mode=clone:stop_duration=2,scale=trunc(iw/2)*2:trunc(ih/2)*2',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', os.path.join(OUT, f'follow_{n}.mp4')])
    rec = {'n': n, 'person': pid, 'what': what, 'place': meta[pid]['place'], 'road': SIDE_NAME[meta[pid]['side']],
           'step_free': TA[pid]['type'] == 'walker_stepfree', 'depart': dep,
           'today_s': round(endA - dep), 'proposal_s': round(endB - dep), 'today_m': round(TA[pid]['length']), 'proposal_m': round(TB[pid]['length'])}
    summary.append(rec); print(rec)
json.dump(summary, open(os.path.join(OUT, 'follow.json'), 'w'), indent=1)
