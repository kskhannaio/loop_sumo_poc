"""Snapshots and side-by-side videos of two scenarios, drawn from the simulation's positions on satellite imagery.

  python scripts/clip.py baseline proposal_151126                        2 minutes from 10:00, every second  -> clip_*
  python scripts/clip.py baseline proposal_151126 --hour                 9:30-10:30, every 2 s, 60x          -> hour_*
  options: --start HH:MM --dur SECONDS --period S --fps N --views C,loop --no-sim (reuse the last recording)

Runs both scenarios (same seed, same traffic) to the end of the window, recording every vehicle and person inside the
loop's area (sumo --fcd-output), then draws a close-up of junction C and the whole loop. The proposal's changes are drawn
under the traffic with their labels on them. Counts at the top: people now on screen, on a crossing, waiting; the hour
version adds people who have crossed so far. Writes report/<second scenario>/<tag>_C.mp4, <tag>_loop.mp4,
still_<tag>_C.png, still_<tag>_loop.png. Then scripts/wait_heat.py and scripts/follow.py use the hour recording.
Needs ffmpeg. Imagery: Esri World Imagery, cached in ~/design_challenge/cache/tiles.
"""
import collections, json, math, os, shutil, subprocess, sys, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from common import BIN, P, cfg, hhmm, JUNCTIONS, run, behaviour_opts, read_net, sumolib
import imagery as PF

C = cfg(); T = C['time']
args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
A, B = args[0], args[1]
HOUR = '--hour' in sys.argv
t0 = hhmm(opt('--start', T['metrics_begin'] if HOUR else '10:00'))
dur = int(opt('--dur', 3600 if HOUR else 120))
period = float(opt('--period', 2 if HOUR else 1))
fps = int(opt('--fps', 30 if HOUR else 8))
tag = 'hour' if HOUR else 'clip'
OUT = P('report', B); os.makedirs(OUT, exist_ok=True)
TMP = P('out', 'clips'); os.makedirs(TMP, exist_ok=True)
LABEL = {'baseline': 'Today'}
LABEL.update({k: v.get('label', k) for k, v in C.get('proposals', {}).items() if not k.startswith('_')})
jl = JUNCTIONS['C']
VIEWS = {'C': ((jl[0] - 0.0006, jl[1] - 0.0016, jl[0] + 0.0021, jl[1] + 0.0004), 19, 760, 1.0),
         'loop': ((77.6128, 12.9228, 77.6232, 12.9318), 17, 760, 2.2)}

# ---- run both scenarios to the end of the window ------------------------------------------------------------------
def simulate(scn):
    d = os.path.join(TMP, scn); os.makedirs(d, exist_ok=True)
    net = read_net(P('net', f'{scn}.net.xml'))
    b = VIEWS['loop'][0]
    corners = [net.convertLonLat2XY(lon, lat) for lon, lat in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))]
    open(os.path.join(d, 'area.add.xml'), 'w').write(           # record only inside the loop's area (keeps the file small)
        '<additional><poly id="area" type="area" color="0,0,0" fill="0" layer="0" shape="' +
        ' '.join(f'{x:.1f},{y:.1f}' for x, y in corners + corners[:1]) + '"/></additional>')
    adds = [P('demand', scn, 'busstops.add.xml'), os.path.join(d, 'area.add.xml')]
    if scn in ('trial_crossings', 'flyover_opened'): adds.append(P('net', 'trial_tls.add.xml'))
    elif os.path.exists(P('net', f'{scn}_tls.add.xml')): adds.append(P('net', f'{scn}_tls.add.xml'))
    cmd = [BIN('sumo'), '-n', P('net', f'{scn}.net.xml'),
           '-r', ','.join(P('demand', scn, f) for f in ('vehicles.rou.xml', 'buses.rou.xml', 'persons.rou.xml')),
           '-a', ','.join(adds), '--begin', str(hhmm(T['sim_begin'])), '--end', str(t0 + dur),
           '--step-length', str(T['step_length_s']), '--lateral-resolution', str(T['lateral_resolution_m']), '--seed', str(T['seed']),
           '--pedestrian.model', 'striping', '--time-to-teleport', '300', '--ignore-route-errors', 'true',
           '--collision.action', 'warn', '--collision.mingap-factor', '0', '--no-step-log', 'true', '--no-warnings', 'true', *behaviour_opts(),
           '--device.fcd.begin', str(t0), '--device.fcd.period', str(period), '--fcd-output.filter-shapes', 'area',
           '--fcd-output', os.path.join(d, f'fcd_{tag}.xml'), '--fcd-output.geo', 'true',
           '--tripinfo-output', os.path.join(d, f'tripinfo_{tag}.xml')]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if '--no-sim' not in sys.argv:
    procs = [simulate(s) for s in (A, B)]
    for p in procs:
        if p.wait(): sys.exit('simulation failed')

def frames(scn):
    """{time: [(kind, lon, lat, angle, speed, id, edge)]}"""
    out, cur = {}, None
    for ev, el in ET.iterparse(os.path.join(TMP, scn, f'fcd_{tag}.xml'), events=('start', 'end')):
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
    im = Image.open(f).convert('L').convert('RGB').resize((width, h))      # grey and dark: photo cars must not look simulated
    im = ImageEnhance.Brightness(im).enhance(0.55)
    return im, lambda lon, lat: ((lon - box[0]) / (box[2] - box[0]) * width, (box[3] - lat) / (box[3] - box[1]) * h), \
        width / ((box[2] - box[0]) * 111320 * k)                       # pixels per metre

on_crossing = lambda edge: edge.startswith(':') and '_c' in edge and '_w' not in edge

def draw(im, proj, ppm, objs, scale, trails, big):
    d = ImageDraw.Draw(im, 'RGBA')
    for pid, pts in trails.items():                                  # where each person has walked recently
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

def font(size, bold=False):
    try: return ImageFont.truetype('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf', size)
    except OSError: return ImageFont.load_default()
FONT, SMALL, TAG = font(20, True), font(14), font(12, True)

def tag_label(d, xy, text, col):
    """a small label with a dark box, centred on xy"""
    w = d.textlength(text, font=TAG); x, y = xy
    d.rectangle([x - w / 2 - 4, y - 9, x + w / 2 + 4, y + 9], fill=(0, 0, 0, 185), outline=col + (255,))
    d.text((x - w / 2, y - 7), text, fill=(255, 255, 255, 255), font=TAG)

def overlay(bg, proj, scn, scale, labels):
    """the proposal's changes under the traffic: drawn zones, modelled new roads, new crossings, new footpath, with labels."""
    spec = C.get('proposals', {}).get(scn)
    if not spec: return bg
    while spec.get('network_from'): spec = C['proposals'][spec['network_from']]
    im = bg.copy(); d = ImageDraw.Draw(im, 'RGBA'); lw = max(2, int(3 * scale / 1.0))
    zones = {k.replace(' ', '').lower(): v for k, v in spec.get('zones', {}).items()}
    fill = {'bus_stop': (255, 146, 43), 'widen_footpath': (81, 207, 102), 'closed_to_traffic': (173, 181, 189)}
    tags = []
    for f in json.load(open(P(spec['file'])))['features']:
        g, pr = f['geometry'], f['properties']
        if g['type'] == 'Polygon':
            act = zones.get((pr.get('label') or '').replace(' ', '').lower())
            if not act: continue
            pts = [proj(*c[:2]) for c in g['coordinates'][0]]
            d.polygon(pts, fill=fill[act] + (100,), outline=fill[act] + (230,))
            area = abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2
            big = area > 900                                        # pixels; small shapes get a label only if large enough
            text = {'bus_stop': 'Bus bay' if big else 'Bus stop', 'widen_footpath': 'Wider footpath',
                    'closed_to_traffic': 'Island, no traffic'}[act]
            cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            tags.append(((cx, cy), text, fill[act], area))
        elif pr.get('change_type') in ('New footpath', 'new road'):
            pts = [proj(*c[:2]) for c in g['coordinates']]
            footpath = pr['change_type'] == 'New footpath'
            col = (81, 207, 102) if footpath else (0, 229, 255)
            for a, b in zip(pts, pts[1:]):                         # dashed
                n = max(1, int(math.dist(a, b) / 8))
                for k in range(0, n, 2):
                    d.line([(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n),
                            (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)], fill=col + (255,), width=lw if footpath else lw * 2)
            f = 0.62 if footpath else 0.5                          # a point that far along the line (the footpath label away from the crossing)
            seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]; goal = f * sum(seg); mid = pts[-1]
            for (a, b), L in zip(zip(pts, pts[1:]), seg):
                if goal <= L: mid = (a[0] + (b[0] - a[0]) * goal / L + (48 if footpath else 0), a[1] + (b[1] - a[1]) * goal / L); break
                goal -= L
            tags.append((mid, 'New footpath' if footpath else 'Slip road', col, 1e9))
    net = sumolib.net.readNet(P('net', f'{scn}.net.xml'), withInternal=True, withPedestrianConnections=True)
    xing = collections.defaultdict(list)
    for e in net.getEdges():
        if e.getID().startswith('proposal_road'):
            d.line([proj(*net.convertXY2LonLat(x, y)) for x, y in e.getShape()], fill=(77, 171, 247, 200), width=lw * 3)
        elif e.getFunction() == 'crossing' and 'pxing' in e.getID():
            pts = [proj(*net.convertXY2LonLat(x, y)) for x, y in e.getShape()]
            d.line(pts, fill=(229, 153, 247, 230), width=lw * 3)
            xing[e.getID().split('_c')[0]] += pts
    for pts in xing.values():
        tags.append(((max(p[0] for p in pts) + 46, sum(p[1] for p in pts) / len(pts)), 'New crossing', (229, 153, 247), 1e9))
    if labels:                                                       # one label per kind and place; skip ones that would overlap
        placed = []
        for (x, y), text, col, _ in sorted(tags, key=lambda t: -t[3]):
            if any(abs(x - px) < 90 and abs(y - py) < 20 for px, py in placed): continue
            if any(t == text and math.dist((x, y), q) < 140 for q, t in placed_text): continue
            tag_label(d, (x, y), text, col); placed.append((x, y)); placed_text.append(((x, y), text))
    return im
placed_text = []

def panel(bg, proj, ppm, objs, title, t, scale, trails, big, crossed):
    for o in objs:
        if o[0] == 'person': trails.setdefault(o[5], []).append((o[1], o[2]))
        if o[0] == 'person' and on_crossing(o[6]): crossed.add(o[5])
    live = {o[5] for o in objs if o[0] == 'person'}
    keep = int(30 / period)
    for pid in list(trails):
        if pid not in live: del trails[pid]
        else: trails[pid] = trails[pid][-keep:]
    im = bg.copy(); draw(im, proj, ppm, objs, scale, trails, big)
    d = ImageDraw.Draw(im, 'RGBA')
    inside = lambda o: 0 <= proj(o[1], o[2])[0] <= im.width and 0 <= proj(o[1], o[2])[1] <= im.height
    seen = [o for o in objs if o[0] == 'person' and inside(o)]
    on_x = sum(1 for o in seen if on_crossing(o[6])); waiting = sum(1 for o in seen if o[4] < 0.1)
    d.rectangle([0, 0, im.width, 56 if HOUR else 34], fill=(0, 0, 0, 170))
    d.text((10, 6), title, fill='white', font=FONT)
    hh, mm, ss = int(t // 3600), int(t % 3600 // 60), int(t % 60)
    d.text((im.width - 380, 9), f"{hh}:{mm:02d}:{ss:02d}   people {len(seen)}   on a crossing {on_x}   waiting {waiting}", fill='white', font=SMALL)
    if HOUR: d.text((10, 34), f"people who have crossed a road here since {T['metrics_begin']}: {len(crossed):,}", fill=(255, 212, 59), font=SMALL)
    return im

def legend(w):
    im = Image.new('RGB', (w, 30), (20, 20, 20)); d = ImageDraw.Draw(im)
    x = 10
    for name, k in (('person walking', 'person'), ('person on a crossing', 'xing'), ('two-wheeler', 'two_wheeler'), ('car / van', 'car'), ('auto', 'auto'), ('bus', 'bus')):
        d.rectangle([x, 9, x + 14, 21], fill=COL[k]); d.text((x + 20, 7), name, fill='white', font=SMALL); x += 30 + 9 * len(name) + 10
    d.text((x + 4, 7), f'white ring: waiting.  Faint lines: last 30 s of walking.  Simulation, not footage; {dur // 60} min at {round(period * fps)}x.',
           fill=(200, 200, 200), font=SMALL)
    return im

only = opt('--views', 'C,loop').split(',')
for name, (box, z, width, scale) in VIEWS.items():
    if name not in only: continue
    bg, proj, ppm = background(box, z, width)
    placed_text.clear(); bgA = overlay(bg, proj, A, scale if name == 'C' else 0.7, name == 'C')
    placed_text.clear(); bgB = overlay(bg, proj, B, scale if name == 'C' else 0.7, name == 'C')
    fdir = os.path.join(TMP, f'frames_{tag}_{name}'); shutil.rmtree(fdir, ignore_errors=True); os.makedirs(fdir)
    leg = legend(2 * width + 10)
    trA, trB, xA, xB = {}, {}, set(), set()
    for i, t in enumerate(times):
        a = panel(bgA, proj, ppm, FA[t], LABEL.get(A, A), t, scale, trA, name == 'C', xA)
        b = panel(bgB, proj, ppm, FB[t], LABEL.get(B, B), t, scale, trB, name == 'C', xB)
        frame = Image.new('RGB', (2 * width + 10, a.height + leg.height), (20, 20, 20))
        frame.paste(a, (0, 0)); frame.paste(b, (width + 10, 0)); frame.paste(leg, (0, a.height))
        frame.save(os.path.join(fdir, f'{i:05d}.png'))
        if i == len(times) // 2: frame.save(os.path.join(OUT, f'still_{"" if tag == "clip" else "hour_"}{name}.png'))
    run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', os.path.join(fdir, '%05d.png'), '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', os.path.join(OUT, f'{tag}_{name}.mp4')])
    print(f"wrote {tag}_{name}.mp4 ({len(times)} frames, {dur // 60} min of simulation at {round(period * fps)}x)")
# where people stood waiting over the hour: scripts/wait_heat.py
