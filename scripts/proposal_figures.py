"""Figures for a drawn-proposal report: before/after at the junction on satellite imagery, the loop's road speeds,
and the change in key measures for each variant.

  python scripts/proposal_figures.py proposal_151126 [variant ...]

Reads the seed runs in out/seeds/ (scripts/seeds.py) and writes report/<proposal>/*.png.
Imagery: Esri World Imagery tiles, cached in ~/design_challenge/cache/tiles (not in the repo).
"""
import csv, io, json, math, os, statistics as st, sys, urllib.request
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Polygon as MPoly
from PIL import Image
from common import P, cfg, carriageways, JUNCTIONS, SIDE_NAME, sumolib

C = cfg()
prop = sys.argv[1] if len(sys.argv) > 1 else 'proposal_151126'
variants = sys.argv[2:]
spec = C['proposals'][prop]
OUT = P('report', prop); os.makedirs(OUT, exist_ok=True)

from imagery import basemap, CREDIT

def label(ax, lon, lat, text, color='white', **kw):
    ax.text(lon, lat, text, color=color, fontsize=kw.pop('fontsize', 8.5), weight='bold', zorder=20,
            bbox=dict(boxstyle='round,pad=0.25', fc=(0, 0, 0, 0.62), ec='none'), **kw)

# ---- data ---------------------------------------------------------------------------------------------------
rn = lambda f: sumolib.net.readNet(f, withInternal=True, withPedestrianConnections=True)      # internal: crossings
base = rn(P('net', 'baseline.net.xml')); pnet = rn(P('net', f'{prop}.net.xml'))
ll = lambda net, pts: [net.convertXY2LonLat(x, y) for x, y in pts]
feats = json.load(open(P(spec['file'])))['features']
pj = json.load(open(P('net', f'{prop}.proposal.json')))
zones = {k.replace(' ', '').lower(): v for k, v in spec.get('zones', {}).items()}

def stops(scn):
    import xml.etree.ElementTree as ET
    net = base if scn == 'baseline' else pnet
    out = []
    for s in ET.parse(P('demand', scn, 'busstops.add.xml')).getroot():
        lane = net.getLane(s.get('lane'))
        a = float(s.get('startPos')); b = float(s.get('endPos'))
        import sumolib
        x, y = sumolib.geomhelper.positionAtShapeOffset(lane.getShape(), (a + b) / 2)
        out.append((s.get('name'), net.convertXY2LonLat(x, y), lane.getEdge().getID()))
    return out

def crossings(net, near, r):
    out = []
    cx, cy = net.convertLonLat2XY(*near)
    for e in net.getEdges():
        if e.getFunction() == 'crossing':
            shp = e.getShape()
            if min(math.dist(p, (cx, cy)) for p in shp) < r: out.append(ll(net, shp))
    return out

# ---- figure 1: before / after at the junction -----------------------------------------------------------------
jl = JUNCTIONS['C']
box = (jl[0] - 0.0006, jl[1] - 0.0016, jl[0] + 0.0021, jl[1] + 0.0004)
fig, axs = plt.subplots(1, 2, figsize=(14, 6.2))
for ax, which in zip(axs, ('today', 'proposal')):
    basemap(ax, box[0], box[1], box[2], box[3], 19)
    net = base if which == 'today' else pnet
    for c in crossings(net, jl, 260):
        xs, ys = zip(*c); ax.plot(xs, ys, color='white', lw=3.2, alpha=0.9, zorder=5, solid_capstyle='butt')
    for name, (lon, lat), _ in stops('baseline' if which == 'today' else prop):
        if box[0] < lon < box[2] and box[1] < lat < box[3]:
            ax.plot(lon, lat, 's', ms=9, mfc='#fcc419', mec='black', zorder=8)
    ax.plot(*jl, 'o', ms=26, mfc='none', mec='#ff6b6b', mew=2.5, zorder=9)
    label(ax, jl[0] + 0.00012, jl[1] + 0.00008, 'C', color='#ff8787', fontsize=11)
    if which == 'today':
        ax.set_title('Today (as modelled)', fontsize=13, loc='left')
        label(ax, box[0] + 0.00004, box[1] + 0.00006, 'White bars: signalised crossings at C.  Yellow squares: bus stops.', fontsize=8)
        continue
    ax.set_title(f"{spec.get('label', prop)} (as modelled)", fontsize=13, loc='left')
    for f in feats:
        g, pr = f['geometry'], f['properties']; kind = pr.get('change_type', '')
        if g['type'] == 'Polygon':
            act = zones.get((pr.get('label') or '').replace(' ', '').lower())
            col = {'bus_stop': '#ff922b', 'widen_footpath': '#51cf66', 'closed_to_traffic': '#adb5bd'}.get(act, '#adb5bd')
            ax.add_patch(MPoly(g['coordinates'][0], closed=True, fc=col, ec=col, alpha=0.45 if act != 'closed_to_traffic' else 0.3,
                               hatch='//' if act == 'closed_to_traffic' else None, zorder=6))
        elif kind.lower() == 'new road':                       # the planner's sketch; the modelled link is drawn below
            xs, ys = zip(*g['coordinates']); ax.plot(xs, ys, color='#4dabf7', lw=1.6, ls=':', zorder=7)
        elif kind == 'New footpath':
            xs, ys = zip(*g['coordinates']); ax.plot(xs, ys, color='#51cf66', lw=3, ls='--', zorder=7)
    for e in pnet.getEdges():
        if e.getID().startswith('proposal_road'):
            xs, ys = zip(*ll(pnet, e.getShape())); ax.plot(xs, ys, color='#4dabf7', lw=4, zorder=7)
            ax.annotate('', xy=(xs[-1], ys[-1]), xytext=(xs[-2], ys[-2]), arrowprops=dict(arrowstyle='-|>', color='#4dabf7', lw=2), zorder=8)
    for e in pnet.getEdges():
        if e.getFunction() == 'crossing' and 'pxing' in e.getID():
            xs, ys = zip(*ll(pnet, e.getShape())); ax.plot(xs, ys, color='#e599f7', lw=5, zorder=8, solid_capstyle='butt')
    key = ['Blue: free-left slip roads (dotted as sketched,', '   solid as modelled: 1 lane, 20 km/h)', 'Pink: new signalised crossings',
           'Orange: bus stop areas (large = off-road bay)', 'Green: wider footpaths, new footpath (dashed)',
           'Grey hatched: islands closed to traffic', '   (no road there today: no change)']
    label(ax, box[0] + 0.00004, box[1] + 0.00006, '\n'.join(key), fontsize=7.2)
axs[-1].text(0.995, 0.005, CREDIT, transform=axs[-1].transAxes, ha='right', va='bottom', fontsize=6.5, color='white')
fig.savefig(os.path.join(OUT, 'junction_before_after.png'), dpi=110, bbox_inches='tight'); plt.close(fig)

# ---- seed averages -------------------------------------------------------------------------------------------
def seed_rows(scn, name):
    root = P('out', 'seeds', scn)
    return [r for s in sorted(os.listdir(root)) if os.path.exists(os.path.join(root, s, 'metrics', name))
            for r in csv.DictReader(open(os.path.join(root, s, 'metrics', name)))]

def speeds(scn):
    acc = {}
    for r in seed_rows(scn, 'vehicles_by_side.csv'):
        if r['avg_speed_kmh']: acc.setdefault((r['side'], r['direction']), []).append(float(r['avg_speed_kmh']))
    return {k: st.mean(v) for k, v in acc.items()}

def along(coords, f):
    """point a fraction f of the way along a lon/lat line"""
    k = math.cos(math.radians(coords[0][1]))
    seg = [math.hypot((b[0] - a[0]) * k, b[1] - a[1]) for a, b in zip(coords, coords[1:])]
    t = f * sum(seg)
    for (a, b), L in zip(zip(coords, coords[1:]), seg):
        if t <= L: return (a[0] + (b[0] - a[0]) * t / L, a[1] + (b[1] - a[1]) * t / L)
        t -= L
    return coords[-1]

# ---- figure 2: loop speeds today vs proposal ---------------------------------------------------------------------
cw = carriageways()
lb = (77.6128, 12.9228, 77.6232, 12.9318)
cmap = LinearSegmentedColormap.from_list('spd', ['#c92a2a', '#f08c00', '#fcc419', '#40c057'])
norm = Normalize(0, 40)
fig, axs = plt.subplots(1, 2, figsize=(13, 6.8))
for ax, scn, title in zip(axs, ('baseline', prop), ('Today', spec.get('label', prop))):
    basemap(ax, *lb, 17)
    sp = speeds(scn)
    for (side, fr, to), coords in cw.items():
        v = sp.get((side, f'{fr}>{to}'))
        xs, ys = zip(*coords)
        ax.plot(xs, ys, color=cmap(norm(v)) if v is not None else '#868e96', lw=5, zorder=5, solid_capstyle='round')
        m = along(coords, 0.3)            # each line runs in its own direction, so the two labels sit apart
        if v is not None: label(ax, m[0], m[1], f"{fr}→{to} {v:.0f}", fontsize=7.5)
    for j, p in JUNCTIONS.items(): label(ax, p[0], p[1], j, color='#ff8787', fontsize=11)
    ax.plot(*JUNCTIONS['C'], 'o', ms=34, mfc='none', mec='white', mew=2, ls='--', zorder=6)
    ax.set_title(f'{title}: average vehicle speed, km/h', fontsize=12, loc='left')
fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axs, shrink=0.55, label='km/h (average of 5 runs, 9:30-10:30 am)')
axs[-1].text(0.995, 0.005, CREDIT, transform=axs[-1].transAxes, ha='right', va='bottom', fontsize=6.5, color='white')
fig.savefig(os.path.join(OUT, 'loop_speeds.png'), dpi=110, bbox_inches='tight'); plt.close(fig)

# ---- figure 3: change against today, per variant ------------------------------------------------------------
def summary(scn):
    rows = seed_rows(scn, 'summary.csv')
    g = lambda k: st.mean(float(r[k]) for r in rows)
    return {'Vehicles leaving C': g('veh_through_C_per_h'), 'Vehicles finishing trips': g('vehicles_finished'),
            'Vehicle delay': g('veh_delay_mean_s'), 'Bus delay': g('bus_delay_mean_s'),
            'Extra walk to cross': g('ped_extra_walk_m_mean'), 'Time lost walking': g('ped_time_lost_mean_s')}
good_up = {'Extra walk to cross': False, 'Time lost walking': False,
           'Vehicles leaving C': True, 'Vehicles finishing trips': True, 'Vehicle delay': False, 'Bus delay': False}
pairs = [(prop, 'baseline')] + [(v, C['proposals'][v].get('compare_with', 'baseline')) for v in variants]
pairs = [(v, b) for v, b in pairs if os.path.isdir(P('out', 'seeds', v)) and os.path.isdir(P('out', 'seeds', b))]
cache = {}
S = lambda s: cache.setdefault(s, summary(s))
measures = list(good_up)
fig, ax = plt.subplots(figsize=(10, 1.2 + 0.42 * len(measures) * len(pairs)))
h = 0.8 / len(pairs)
pal = ['#e8590c', '#1c7ed6', '#2f9e44', '#7048e8', '#c2255c']
for i, (v, b) in enumerate(pairs):
    ch = [(S(v)[m] - S(b)[m]) / S(b)[m] * 100 for m in measures]
    ys = [k + i * h for k in range(len(measures))]
    ax.barh(ys, ch, h, color=pal[i % len(pal)], label=C['proposals'][v].get('label', v) + ('' if b == 'baseline' else f" (vs {C['proposals'][b].get('label', b)})"))
    for y, c, m in zip(ys, ch, measures):
        better = (c > 0) == good_up[m]
        ax.text(c + (1 if c >= 0 else -1), y, f"{c:+.0f}%", va='center', ha='left' if c >= 0 else 'right', fontsize=7.5,
                color='#2b8a3e' if better and abs(c) >= 0.5 else '#c92a2a' if abs(c) >= 0.5 else '#495057')
ax.set_yticks([k + h * (len(pairs) - 1) / 2 for k in range(len(measures))])
ax.set_yticklabels([m + (' (higher is better)' if good_up[m] else ' (lower is better)') for m in measures])
ax.invert_yaxis(); ax.axvline(0, color='black', lw=0.8)
ax.set_xlabel('change against today, % (average of 5 runs)')
lim = max(abs(x) for x in ax.get_xlim()); ax.set_xlim(-lim * 1.15, lim * 1.15)
ax.legend(loc='lower right', fontsize=8); ax.grid(axis='x', alpha=0.3)
ax.set_title('Change against today (pedestrian measures first; vehicle measures are not calibrated)', loc='left', fontsize=11)
plt.tight_layout(); fig.savefig(os.path.join(OUT, 'changes.png'), dpi=110); plt.close(fig)
json.dump({s: S(s) for s in cache}, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1)
print('wrote', OUT)
