"""How far you can walk in 5 minutes from a bus stop, today against a proposal, from the street network alone.

  python scripts/walk_reach.py proposal_151126

Starting points: the hospital side of Hosur Road and of Sarjapura Road, where the proposal adds crossings.
Walking graph: every footpath, footway, stair, crossing and junction corner (walking area) in the SUMO network, walkable
in both directions at 1.2 m/s (stairs 0.5 m/s). At a signalised crossing the walker waits the average time for the
green, worked out from the signal plan: (red time)^2 / (2 x cycle). No crowding and no vehicles: this is the street's
layout and signals only. Writes report/<proposal>/walk_reach.png and walk_reach.json.
"""
import collections, heapq, json, math, os, sys
import xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
from common import P, cfg, sumolib
from imagery import basemap, CREDIT

C = cfg()
prop = sys.argv[1] if len(sys.argv) > 1 else 'proposal_151126'
OUT = P('report', prop); os.makedirs(OUT, exist_ok=True)
WALK = C['pedestrians']['walking_speed_mps']; STAIRS = C['network']['foot_over_bridges']['stairs_speed_mps']
# hospital side of each road, where the proposal's new crossings land (today there is no crossing there)
ORIGINS = {'Hospital side of Hosur Road, 120 m south of C': (77.61568, 12.92893),
           'Hospital side of Sarjapura Road, 105 m east of C': (77.61594, 12.92932)}
BANDS = [0, 60, 120, 180, 240, 300]                                    # seconds
LABEL = {'baseline': 'Today', prop: C['proposals'][prop].get('label', prop)}

def tls_waits(path, tls_add=None):
    """{crossing edge id: average wait s} from the static or base program of each signal."""
    root = ET.parse(path).getroot()
    progs = {t.get('id'): t for t in root.findall('tlLogic')}
    if tls_add and os.path.exists(tls_add):
        for t in ET.parse(tls_add).getroot().findall('tlLogic'): progs[t.get('id')] = t
    waits = {}
    for c in root.findall('connection'):
        tl, via = c.get('tl'), c.get('to')
        if not tl or not via or not via.startswith(':') or '_c' not in via: continue
        ph = [(float(p.get('duration')), p.get('state')) for p in progs[tl].findall('phase')]
        i = int(c.get('linkIndex')); T = sum(d for d, _ in ph)
        green = sum(d for d, s in ph if i < len(s) and s[i] in 'Gg')
        red = T - green
        waits[via] = max(waits.get(via, 0), red * red / (2 * T) if T else 0)
    return waits

def graph(scn):
    """Walking graph whose points are junction corners (walking areas) and footpath ends; links are footpaths, footways,
    stairs and crossings, each with its walking time (crossings add the average signal wait)."""
    net = sumolib.net.readNet(P('net', f'{scn}.net.xml'), withInternal=True, withPedestrianConnections=True)
    waits = tls_waits(P('net', f'{scn}.net.xml'), P('net', f'{scn}_tls.add.xml'))
    ped = {}
    for e in net.getEdges(withInternal=True):
        lanes = [l for l in e.getLanes() if l.allows('pedestrian')]
        if lanes and e.getFunction() != 'walkingarea':
            speed = STAIRS if e.getType() == 'highway.steps' else WALK
            ped[e.getID()] = dict(cost=e.getLength() / speed, wait=waits.get(e.getID(), 0), shape=lanes[0].getShape(), edge=e,
                                  a=('end', e.getID(), 0), b=('end', e.getID(), 1))
    for c in ET.parse(P('net', f'{scn}.net.xml')).getroot().findall('connection'):
        f, t = c.get('from'), c.get('to')
        if t and t.startswith(':') and '_w' in t and f in ped: ped[f]['b'] = t        # footpath/crossing end meets a corner
        if f and f.startswith(':') and '_w' in f and t in ped: ped[t]['a'] = f
    adj = collections.defaultdict(list)
    for eid, d in ped.items():
        c = d['cost'] + d['wait']
        adj[d['a']].append((d['b'], c)); adj[d['b']].append((d['a'], c))          # people walk both ways
    return net, ped, adj

def reach(net, ped, adj, lonlat):
    """{point: seconds} from the nearest footpath to lonlat."""
    x, y = net.convertLonLat2XY(*lonlat)
    start = min((e for e in ped if not e.startswith(':')), key=lambda e: sumolib.geomhelper.distancePointToPolygon((x, y), ped[e]['shape']))
    d = ped[start]; f = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint((x, y), d['shape']) / max(1e-6, sumolib.geomhelper.polyLength(d['shape']))
    best = {d['a']: f * d['cost'], d['b']: (1 - f) * d['cost']}
    pq = [(v, k) for k, v in best.items()]; heapq.heapify(pq)
    while pq:
        t, v = heapq.heappop(pq)
        if t > best.get(v, 1e9) or t > BANDS[-1] + 60: continue
        for n, c in adj[v]:
            if t + c < best.get(n, 1e9): best[n] = t + c; heapq.heappush(pq, (t + c, n))
    return best

def pieces(d, ta, tb, step=6.0):
    """split a footpath into short pieces, each with the time to reach it from whichever end is quicker."""
    shp = d['shape']; L = sumolib.geomhelper.polyLength(shp) or 1; n = max(1, int(L // step))
    speed = d['cost'] / L if L else 1
    for k in range(n):
        s0, s1 = k * L / n, (k + 1) * L / n
        mid = (s0 + s1) / 2
        t = min(ta + d['wait'] + mid * speed, tb + d['wait'] + (L - mid) * speed)
        yield [sumolib.geomhelper.positionAtShapeOffset(shp, s0), sumolib.geomhelper.positionAtShapeOffset(shp, s1)], t, s1 - s0

cmap = ListedColormap(['#2b8a3e', '#74b816', '#fab005', '#f76707', '#e03131'])
norm = BoundaryNorm(BANDS, cmap.N)
box = (77.6128, 12.9238, 77.6200, 12.9318)
G = {s: graph(s) for s in ('baseline', prop)}
summary = {}
fig, axs = plt.subplots(len(ORIGINS), 2, figsize=(13, 6.6 * len(ORIGINS)))
for row, (oname, ll) in enumerate(ORIGINS.items()):
    for col, scn in enumerate(('baseline', prop)):
        ax = axs[row][col]; net, ped, adj = G[scn]
        basemap(ax, *box, 17)
        ax.imshow([[0]], extent=(box[0], box[2], box[1], box[3]), cmap='gray', alpha=0.45, vmin=0, vmax=1,
                  aspect=1 / math.cos(math.radians(12.927)), zorder=1)              # dim the photo
        t = reach(net, ped, adj, ll)
        metres = 0.0
        for eid, d in ped.items():
            ta, tb = t.get(d['a'], 1e9), t.get(d['b'], 1e9)
            if min(ta, tb) > BANDS[-1]: continue
            for seg, s, L in pieces(d, ta, tb):
                if s > BANDS[-1]: continue
                (x0, y0), (x1, y1) = [net.convertXY2LonLat(*p) for p in seg]
                ax.plot([x0, x1], [y0, y1], color=cmap(norm(s)), lw=2.4, solid_capstyle='round', zorder=3)
                if not eid.startswith(':'): metres += L
        ax.plot(*ll, marker='*', ms=18, color='white', mec='black', zorder=5)
        ax.set_title(f"{LABEL[scn]}\nfrom the {oname[0].lower() + oname[1:]}", fontsize=10.5, loc='left')
        ax.text(0.01, 0.01, f"Footpath within 5 min: {metres / 1000:.1f} km", transform=ax.transAxes, color='white', fontsize=10, weight='bold',
                bbox=dict(fc=(0, 0, 0, 0.65), ec='none'), zorder=6)
        summary.setdefault(oname, {})[scn] = round(metres)
axs[-1][-1].text(0.995, 0.005, CREDIT, transform=axs[-1][-1].transAxes, ha='right', va='bottom', fontsize=6.5, color='white')
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axs, shrink=0.35, ticks=BANDS, pad=0.03)
cb.ax.set_yticklabels([f'{b // 60} min' for b in BANDS]); cb.set_label('walking time from the star, including average signal waits')
fig.savefig(os.path.join(OUT, 'walk_reach.png'), dpi=100, bbox_inches='tight'); plt.close(fig)
json.dump(summary, open(os.path.join(OUT, 'walk_reach.json'), 'w'), indent=1)
print(summary)
