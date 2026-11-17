"""Where people stood waiting around junction C over the recorded hour, today against a proposal.

  python scripts/wait_heat.py baseline proposal_151126

Reads the full-hour recording made by `clip.py ... --hour` (out/clips/<scenario>/fcd_hour.xml). Every 2 s, each person
standing still (under 0.1 m/s) adds 2 s to the 8 m square they stand in. Writes report/<second scenario>/wait_heat.png
and wait_heat.json (person-minutes of waiting in the picture, per scenario).
"""
import json, math, os, sys, xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import P, cfg, JUNCTIONS
import imagery as PF

C = cfg(); T = C['time']
A, B = sys.argv[1], sys.argv[2]
OUT = P('report', B)
LABEL = {'baseline': 'Today', **{k: v.get('label', k) for k, v in C['proposals'].items() if not k.startswith('_')}}
jl = JUNCTIONS['C']
box = (jl[0] - 0.0006, jl[1] - 0.0016, jl[0] + 0.0021, jl[1] + 0.0004)
k = math.cos(math.radians(jl[1]))
CELL = 8.0                                                                   # metres
nx = int((box[2] - box[0]) * 111320 * k / CELL); ny = int((box[3] - box[1]) * 110574 / CELL)

def heat(scn):
    H = np.zeros((ny, nx)); prev = None; dt = 2.0
    for ev, el in ET.iterparse(P('out', 'clips', scn, 'fcd_hour.xml'), events=('start', 'end')):
        if ev == 'start' and el.tag == 'timestep':
            t = float(el.get('time')); dt = t - prev if prev is not None else dt; prev = t
        elif ev == 'end' and el.tag == 'person':
            lon, lat, v = float(el.get('x')), float(el.get('y')), float(el.get('speed') or 0)
            if v < 0.1 and box[0] <= lon < box[2] and box[1] <= lat < box[3]:
                H[int((box[3] - lat) / (box[3] - box[1]) * ny), int((lon - box[0]) / (box[2] - box[0]) * nx)] += dt
        elif ev == 'end' and el.tag == 'timestep': el.clear()
    return H / 60

HA, HB = heat(A), heat(B)
vmax = np.percentile(np.concatenate([HA[HA > 0], HB[HB > 0]]), 99)
fig, axs = plt.subplots(1, 2, figsize=(14, 5.4))
for ax, H, scn in zip(axs, (HA, HB), (A, B)):
    PF.basemap(ax, *box, 19)
    ax.imshow(np.zeros((2, 2)), extent=(box[0], box[2], box[1], box[3]), cmap='gray', alpha=0.55, vmin=0, vmax=1, aspect=1 / k)
    im = ax.imshow(np.ma.masked_less(H, 1), extent=(box[0], box[2], box[1], box[3]), cmap='plasma', vmin=1, vmax=vmax, alpha=0.95,
                   aspect=1 / k, interpolation='nearest')
    ax.set_title(f"{LABEL.get(scn, scn)}: {H.sum():,.0f} person-minutes of waiting", loc='left', fontsize=11)
fig.colorbar(im, ax=axs, shrink=0.85, label=f'person-minutes standing still per {CELL:.0f} m square, {T["metrics_begin"]}–{T["metrics_end"]}', extend='max')
axs[1].text(0.995, 0.005, PF.CREDIT, transform=axs[1].transAxes, ha='right', va='bottom', fontsize=6.5, color='white')
fig.savefig(os.path.join(OUT, 'wait_heat.png'), dpi=110, bbox_inches='tight'); plt.close(fig)
res = {s: round(float(H.sum())) for s, H in ((A, HA), (B, HB))}
json.dump(res, open(os.path.join(OUT, 'wait_heat.json'), 'w')); print(res)
