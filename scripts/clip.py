"""Snapshots and a side-by-side video of two scenarios, drawn from the simulation's vehicle positions.

  python scripts/clip.py baseline proposal_151126 [start=10:00] [seconds=120]

Runs both scenarios (same seed, same traffic) up to start + seconds, recording every vehicle and person each second
over that window (sumo --fcd-output), then draws them on satellite imagery: a close-up of junction C and the whole loop.
Writes report/<second scenario>/clip_C.mp4, clip_loop.mp4 and still_C.png, still_loop.png (the middle of the window).
Needs ffmpeg. Imagery: Esri World Imagery, cached in ~/design_challenge/cache/tiles.
"""
import math, os, shutil, subprocess, sys, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from common import BIN, P, cfg, hhmm, JUNCTIONS, run
import imagery as PF

C = cfg(); T = C['time']
A, B = sys.argv[1], sys.argv[2]
t0 = hhmm(sys.argv[3]) if len(sys.argv) > 3 else hhmm('10:00')
dur = int(sys.argv[4]) if len(sys.argv) > 4 else 120
OUT = P('report', B); os.makedirs(OUT, exist_ok=True)
TMP = P('out', 'clips'); os.makedirs(TMP, exist_ok=True)
LABEL = {'baseline': 'Today'}
LABEL.update({k: v.get('label', k) for k, v in C.get('proposals', {}).items() if not k.startswith('_')})

# ---- run both scenarios up to the end of the window ------------------------------------------------------------
def simulate(scn):
    d = os.path.join(TMP, scn); os.makedirs(d, exist_ok=True)
    adds = [P('demand', scn, 'busstops.add.xml')]
    if scn in ('trial_crossings', 'flyover_opened'): adds.append(P('net', 'trial_tls.add.xml'))
    elif os.path.exists(P('net', f'{scn}_tls.add.xml')): adds.append(P('net', f'{scn}_tls.add.xml'))
    cmd = [BIN('sumo'), '-n', P('net', f'{scn}.net.xml'),
           '-r', ','.join(P('demand', scn, f) for f in ('vehicles.rou.xml', 'buses.rou.xml', 'persons.rou.xml')),
           '-a', ','.join(adds), '--begin', str(hhmm(T['sim_begin'])), '--end', str(t0 + dur),
           '--step-length', str(T['step_length_s']), '--lateral-resolution', str(T['lateral_resolution_m']), '--seed', str(T['seed']),
           '--pedestrian.model', 'striping', '--time-to-teleport', '300', '--ignore-route-errors', 'true',
           '--collision.action', 'warn', '--collision.mingap-factor', '0', '--no-step-log', 'true', '--no-warnings', 'true',
           '--device.fcd.begin', str(t0), '--device.fcd.period', '1', '--fcd-output', os.path.join(d, 'fcd.xml'), '--fcd-output.geo', 'true']
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if '--no-sim' not in sys.argv:
    procs = [simulate(s) for s in (A, B)]
    for p in procs:
        if p.wait(): sys.exit('simulation failed')

def frames(scn):
    """{time: [(kind, lon, lat, angle, speed, id, edge)]}"""
    out, cur = {}, None
    for ev, el in ET.iterparse(os.path.join(TMP, scn, 'fcd.xml'), events=('start', 'end')):
        if ev == 'start' and el.tag == 'timestep': cur = float(el.get('time')); out[cur] = []
        elif ev == 'end' and el.tag in ('vehicle', 'person'):
            kind = 'person' if el.tag == 'person' else (el.get('type') or '').split('@')[0]
            out[cur].append((kind, float(el.get('x')), float(el.get('y')), float(el.get('angle') or 0), float(el.get('speed') or 0),
                             el.get('id'), el.get('edge') or el.get('lane') or ''))
        elif ev == 'end' and el.tag == 'timestep': el.clear()
    return out

FA, FB = frames(A), frames(B)
times = sorted(t for t in FA if t in FB and t0 <= t <= t0 + dur)

# ---- drawing ---------------------------------------------------------------------------------------------------
SIZE = {'two_wheeler': (2.0, 0.8), 'car': (4.3, 1.8), 'van_maxicab': (4.8, 1.9), 'auto': (2.7, 1.4), 'goods_auto': (3.0, 1.5),
        'lcv': (5.5, 2.0), 'truck': (8.0, 2.5), 'bus': (12.0, 2.6)}
COL = {'two_wheeler': (255, 146, 43), 'car': (77, 171, 247), 'van_maxicab': (77, 171, 247), 'auto': (81, 207, 102),
       'goods_auto': (81, 207, 102), 'lcv': (200, 200, 200), 'truck': (200, 200, 200), 'bus': (250, 82, 82), 'person': (240, 101, 255),
       'xing': (255, 212, 59)}

def background(box, z, width):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    k = math.cos(math.radians((box[1] + box[3]) / 2))
    h = int(width * (box[3] - box[1]) / ((box[2] - box[0]) * k))
    fig = plt.figure(figsize=(width / 100, h / 100), dpi=100); ax = fig.add_axes([0, 0, 1, 1])
    PF.basemap(ax, *box, z); ax.axis('off')
    f = os.path.join(TMP, f'bg_{z}_{width}.png'); fig.savefig(f, dpi=100); plt.close(fig)
    from PIL import ImageEnhance
    im = Image.open(f).convert('L').convert('RGB').resize((width, h))      # grey and dark: photo cars must not look simulated
    im = ImageEnhance.Brightness(im).enhance(0.55)
    return im, lambda lon, lat: ((lon - box[0]) / (box[2] - box[0]) * width, (box[3] - lat) / (box[3] - box[1]) * h), \
        width / ((box[2] - box[0]) * 111320 * k)                       # pixels per metre

on_crossing = lambda edge: edge.startswith(':') and '_c' in edge and '_w' not in edge

def draw(im, proj, ppm, objs, scale, trails, big):
    d = ImageDraw.Draw(im, 'RGBA')
    for pid, pts in trails.items():                                  # where each person has walked in the last 30 s
        if len(pts) > 1: d.line([proj(*p) for p in pts], fill=(240, 101, 255, 90), width=2 if big else 1)
    people = []
    for kind, lon, lat, ang, spd, oid, edge in objs:
        x, y = proj(lon, lat)
        if not (-20 < x < im.width + 20 and -20 < y < im.height + 20): continue
        if kind == 'person': people.append((x, y, spd, edge)); continue
        L, W = SIZE.get(kind, (4.3, 1.8)); L, W = max(L * ppm * scale, 3), max(W * ppm * scale, 2)
        a = math.radians(ang)                                        # SUMO angle: degrees clockwise from north
        dx, dy = math.sin(a), -math.cos(a); nx, ny = -dy, dx
        pts = [(x + dx * L / 2 * s1 + nx * W / 2 * s2, y + dy * L / 2 * s1 + ny * W / 2 * s2) for s1, s2 in ((1, 1), (1, -1), (-1, -1), (-1, 1))]
        d.polygon(pts, fill=COL.get(kind, (200, 200, 200)) + (200,), outline=(0, 0, 0, 255) if spd < 0.5 else None)
    for x, y, spd, edge in people:                                   # people on top, large
        r = 4.0 if big else 2.2
        col = (255, 212, 59, 255) if on_crossing(edge) else COL['person'] + (255,)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col, outline=(255, 255, 255, 255) if spd < 0.1 else None)

try: FONT = ImageFont.truetype('DejaVuSans-Bold.ttf', 20); SMALL = ImageFont.truetype('DejaVuSans.ttf', 14)
except OSError: FONT = SMALL = ImageFont.load_default()

def overlay(bg, proj, scn, scale):
    """the proposal's changes under the traffic: drawn zones, modelled new roads, new crossings, new footpath."""
    spec = C.get('proposals', {}).get(scn)
    if not spec: return bg
    while spec.get('network_from'): spec = C['proposals'][spec['network_from']]
    import json, sumolib
    im = bg.copy(); d = ImageDraw.Draw(im, 'RGBA'); lw = max(2, int(3 * scale / 1.0))
    zones = {k.replace(' ', '').lower(): v for k, v in spec.get('zones', {}).items()}
    fill = {'bus_stop': (255, 146, 43, 110), 'widen_footpath': (81, 207, 102, 110), 'closed_to_traffic': (173, 181, 189, 90)}
    for f in json.load(open(P(spec['file'])))['features']:
        g, pr = f['geometry'], f['properties']
        if g['type'] == 'Polygon':
            act = zones.get((pr.get('label') or '').replace(' ', '').lower())
            if act: d.polygon([proj(*c[:2]) for c in g['coordinates'][0]], fill=fill[act], outline=fill[act][:3] + (230,))
        elif pr.get('change_type') in ('New footpath', 'new road'):
            pts = [proj(*c[:2]) for c in g['coordinates']]
            col = (81, 207, 102, 255) if pr['change_type'] == 'New footpath' else (0, 229, 255, 255)
            for a, b in zip(pts, pts[1:]):                         # dashed
                n = max(1, int(math.dist(a, b) / 8))
                for k in range(0, n, 2):
                    d.line([(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n),
                            (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)], fill=col, width=lw if col[1] == 207 else lw * 2)
    net = sumolib.net.readNet(P('net', f'{scn}.net.xml'), withInternal=True, withPedestrianConnections=True)
    for e in net.getEdges():
        if e.getID().startswith('proposal_road'):
            d.line([proj(*net.convertXY2LonLat(x, y)) for x, y in e.getShape()], fill=(77, 171, 247, 200), width=lw * 3)
        elif e.getFunction() == 'crossing' and 'pxing' in e.getID():
            d.line([proj(*net.convertXY2LonLat(x, y)) for x, y in e.getShape()], fill=(229, 153, 247, 230), width=lw * 3)
    return im

def panel(bg, proj, ppm, objs, title, t, scale, trails, big):
    for o in objs:
        if o[0] == 'person': trails.setdefault(o[5], []).append((o[1], o[2]))
    live = {o[5] for o in objs if o[0] == 'person'}
    for pid in list(trails):
        if pid not in live: del trails[pid]
        else: trails[pid] = trails[pid][-30:]
    im = bg.copy(); draw(im, proj, ppm, objs, scale, trails, big)
    d = ImageDraw.Draw(im, 'RGBA')
    seen = [o for o in objs if o[0] == 'person' and 0 <= proj(o[1], o[2])[0] <= im.width and 0 <= proj(o[1], o[2])[1] <= im.height]
    moving = len(seen); still = sum(1 for o in seen if on_crossing(o[6]))
    waiting = sum(1 for o in seen if o[4] < 0.1)
    d.rectangle([0, 0, im.width, 34], fill=(0, 0, 0, 170))
    d.text((10, 6), title, fill='white', font=FONT)
    hh, mm, ss = int(t // 3600), int(t % 3600 // 60), int(t % 60)
    d.text((im.width - 380, 9), f"{hh}:{mm:02d}:{ss:02d}   people {moving}   on a crossing {still}   waiting {waiting}", fill='white', font=SMALL)
    return im

def legend(w):
    im = Image.new('RGB', (w, 30), (20, 20, 20)); d = ImageDraw.Draw(im)
    x = 10
    for name, k in (('person walking', 'person'), ('person on a crossing', 'xing'), ('two-wheeler', 'two_wheeler'), ('car / van', 'car'), ('auto', 'auto'), ('bus', 'bus')):
        d.rectangle([x, 9, x + 14, 21], fill=COL[k]); d.text((x + 20, 7), name, fill='white', font=SMALL); x += 30 + 9 * len(name) + 10
    d.text((x + 4, 7), 'white ring: person waiting.  Faint lines: last 30 s of walking.  Simulation, not footage.', fill=(200, 200, 200), font=SMALL)
    return im

def legend2(w):
    im = Image.new('RGB', (w, 26), (20, 20, 20)); d = ImageDraw.Draw(im); x = 10
    for name, col in (('slip road (dashed: as sketched)', (0, 229, 255)), ('new signalised crossing', (229, 153, 247)), ('bus stop area', (255, 146, 43)),
                      ('wider footpath / new footpath', (81, 207, 102)), ('islands closed to traffic', (173, 181, 189))):
        d.rectangle([x, 7, x + 14, 19], fill=col); d.text((x + 20, 5), name, fill='white', font=SMALL); x += 34 + 8 * len(name)
    return im

jl = JUNCTIONS['C']
VIEWS = {'C': ((jl[0] - 0.0006, jl[1] - 0.0016, jl[0] + 0.0021, jl[1] + 0.0004), 19, 760, 1.0),
         'loop': ((77.6128, 12.9228, 77.6232, 12.9318), 17, 760, 2.2)}
for name, (box, z, width, scale) in VIEWS.items():
    bg, proj, ppm = background(box, z, width)
    bgA, bgB = overlay(bg, proj, A, scale if name == 'C' else 0.7), overlay(bg, proj, B, scale if name == 'C' else 0.7)
    fdir = os.path.join(TMP, f'frames_{name}'); shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
    l1, l2 = legend(2 * width + 10), legend2(2 * width + 10)
    leg = Image.new('RGB', (l1.width, l1.height + l2.height)); leg.paste(l1, (0, 0)); leg.paste(l2, (0, l1.height))
    trA, trB = {}, {}
    for i, t in enumerate(times):
        a = panel(bgA, proj, ppm, FA[t], LABEL.get(A, A), t, scale, trA, name == 'C'); b = panel(bgB, proj, ppm, FB[t], LABEL.get(B, B), t, scale, trB, name == 'C')
        frame = Image.new('RGB', (2 * width + 10, a.height + leg.height), (20, 20, 20))
        frame.paste(a, (0, 0)); frame.paste(b, (width + 10, 0)); frame.paste(leg, (0, a.height))
        frame.save(os.path.join(fdir, f'{i:05d}.png'))
        if i == len(times) // 2: frame.save(os.path.join(OUT, f'still_{name}.png'))
    run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '8', '-i', os.path.join(fdir, '%05d.png'), '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', os.path.join(OUT, f'clip_{name}.mp4')])
    print(f"wrote clip_{name}.mp4 ({len(times)} s of simulation at 8x) and still_{name}.png")
