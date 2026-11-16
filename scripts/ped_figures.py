"""Pedestrian results of a drawn proposal against today, averaged over the seed runs (out/seeds/).

  python scripts/ped_figures.py proposal_151126 [variant ...]

Writes report/<proposal>/where_people_cross.png (people crossing per hour at each crossing, today vs proposal, on
imagery), walking.png (extra walk and time lost per road, per scenario) and ped_summary.json.
"""
import csv, json, math, os, statistics as st, sys, xml.etree.ElementTree as ET
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import P, cfg, JUNCTIONS, SIDE_NAME, sumolib
from imagery import basemap, CREDIT

C = cfg()
prop = sys.argv[1] if len(sys.argv) > 1 else 'proposal_151126'
scns = ['baseline', prop] + [v for v in sys.argv[2:] if os.path.isdir(P('out', 'seeds', v))]
LABEL = {'baseline': 'Today', **{k: v.get('label', k) for k, v in C['proposals'].items() if not k.startswith('_')}}
OUT = P('report', prop); os.makedirs(OUT, exist_ok=True)
seeds = lambda scn: [s for s in sorted(os.listdir(P('out', 'seeds', scn)), key=int)
                     if os.path.exists(P('out', 'seeds', scn, s, 'metrics', 'summary.csv'))]

def rows(scn, name):
    return [r for s in seeds(scn) for r in csv.DictReader(open(P('out', 'seeds', scn, s, 'metrics', name)))]

# ---- per road: extra walk, time lost, time to cross -------------------------------------------------------------
roads = {}
for scn in scns:
    acc = {}
    for r in rows(scn, 'people_by_side.csv'):
        a = acc.setdefault(r['side'], {'extra_walk_m': [], 'time_lost_s': [], 'trip_s': [], 'trip_p85_s': [], 'people': []})
        a['extra_walk_m'].append(float(r['extra_walk_m_mean'])); a['time_lost_s'].append(float(r['time_lost_mean_s']))
        a['trip_s'].append(float(r['trip_time_mean_s'])); a['trip_p85_s'].append(float(r['trip_time_p85_s'])); a['people'].append(float(r['people']))
    roads[scn] = {side: {k: (round(st.mean(v), 1), round(min(v), 1), round(max(v), 1)) for k, v in a.items()} for side, a in acc.items()}

# ---- where people cross: people per hour on each crossing, grouped by junction or crossing site --------------------
def crossing_use(scn):
    net = sumolib.net.readNet(P('net', f'{scn}.net.xml'), withInternal=True, withPedestrianConnections=True)
    pos = {}
    for e in net.getEdges():
        if e.getFunction() == 'crossing':
            shp = e.getShape(); node = e.getID()[1:e.getID().rindex('_c')]
            pos[e.getID()] = (node, net.convertXY2LonLat(*shp[len(shp) // 2]))
    per_seed = []
    for s in seeds(scn):
        n = {}
        for iv in ET.parse(P('out', 'seeds', scn, s, scn, 'edgedata_people.xml')).getroot().findall('interval'):
            for e in iv.findall('edge'):
                if e.get('id') in pos: n[e.get('id')] = n.get(e.get('id'), 0) + float(e.get('entered') or 0)
        per_seed.append(n)
    out = {}
    for eid, (node, ll) in pos.items():
        v = st.mean(d.get(eid, 0) for d in per_seed) if per_seed else 0
        if v <= 0: continue
        o = out.setdefault(node, {'people_h': 0, 'pts': []}); o['people_h'] += v; o['pts'].append(ll)
    for o in out.values():
        o['lonlat'] = (st.mean(p[0] for p in o['pts']), st.mean(p[1] for p in o['pts'])); del o['pts']
    return out

use = {scn: crossing_use(scn) for scn in ('baseline', prop)}
new_sites = {k: v for k, v in use[prop].items() if 'pxing' in k}

lb = (77.6128, 12.9228, 77.6232, 12.9318)
fig, axs = plt.subplots(1, 2, figsize=(13, 6.8))
for ax, scn in zip(axs, ('baseline', prop)):
    basemap(ax, *lb, 17)
    for node, o in use[scn].items():
        lon, lat = o['lonlat']
        if not (lb[0] < lon < lb[2] and lb[1] < lat < lb[3]) or o['people_h'] < 20: continue
        new = 'pxing' in node
        ax.scatter(lon, lat, s=o['people_h'] / 2.5, c='#e599f7' if new else '#4dabf7', alpha=0.75, edgecolors='white', linewidths=1, zorder=5)
        if o['people_h'] >= 250 or new:
            ax.text(lon, lat, f"{o['people_h']:.0f}", fontsize=7.5, color='white', weight='bold', ha='center', va='center', zorder=6)
    for j, p in JUNCTIONS.items():
        ax.text(p[0] + 0.0003, p[1] + 0.0002, j, color='#ff8787', fontsize=12, weight='bold', zorder=7,
                bbox=dict(boxstyle='round,pad=0.2', fc=(0, 0, 0, 0.6), ec='none'))
    ax.set_title(f"{LABEL[scn]}: people crossing per hour", fontsize=12, loc='left')
axs[1].text(0.01, 0.01, 'Blue: existing crossings and foot over bridges.  Pink: new crossings.\nCircle size = people per hour (average of 5 runs).',
            transform=axs[1].transAxes, fontsize=8, color='white', va='bottom', bbox=dict(fc=(0, 0, 0, 0.62), ec='none'))
axs[1].text(0.995, 0.005, CREDIT, transform=axs[1].transAxes, ha='right', va='bottom', fontsize=6.5, color='white')
fig.savefig(os.path.join(OUT, 'where_people_cross.png'), dpi=110, bbox_inches='tight'); plt.close(fig)

# ---- walking: extra walk and time lost per road ---------------------------------------------------------------------
fig, axs = plt.subplots(1, 2, figsize=(12, 3.8))
sides = ['BC', 'CA', 'AB']
pal = ['#868e96', '#e8590c', '#1c7ed6', '#2f9e44']
w = 0.8 / len(scns)
for ax, key, title in zip(axs, ('extra_walk_m', 'time_lost_s'), ('Extra walk to reach a crossing, m', 'Time lost while walking (waiting, detours), s')):
    for i, scn in enumerate(scns):
        vals = [roads[scn][s][key] for s in sides]
        xs = [k + i * w for k in range(len(sides))]
        ax.bar(xs, [v[0] for v in vals], w, color=pal[i % len(pal)], label=LABEL[scn],
               yerr=[[v[0] - v[1] for v in vals], [v[2] - v[0] for v in vals]], capsize=2, error_kw=dict(lw=0.8))
        for x, v in zip(xs, vals): ax.text(x, v[0] + 4, f"{v[0]:.0f}", ha='center', fontsize=7.5)
    ax.set_xticks([k + w * (len(scns) - 1) / 2 for k in range(len(sides))]); ax.set_xticklabels([SIDE_NAME[s] for s in sides])
    ax.set_title(title, loc='left', fontsize=11); ax.grid(axis='y', alpha=0.3); ax.spines[['top', 'right']].set_visible(False)
axs[0].legend(fontsize=8)
fig.text(0.01, -0.02, 'Bars: average of 5 runs; whiskers: lowest and highest run. 9:30-10:30 am.', fontsize=8, color='#555')
plt.tight_layout(); fig.savefig(os.path.join(OUT, 'walking.png'), dpi=110, bbox_inches='tight'); plt.close(fig)

json.dump({'roads': roads, 'new_crossings_people_h': {k: round(v['people_h']) for k, v in new_sites.items()},
           'crossing_use': {s: {k: round(v['people_h']) for k, v in u.items() if v['people_h'] >= 20} for s, u in use.items()}},
          open(os.path.join(OUT, 'ped_summary.json'), 'w'), indent=1)
print(json.dumps({'roads': roads, 'new': {k: round(v['people_h']) for k, v in new_sites.items()}}, indent=0)[:3000])
