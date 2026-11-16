"""Step 2 - scenario networks.

baseline         = net/base.net.xml (crossings only where netconvert guessed them at junctions)
trial_crossings  = base + signalised mid-block crossings at config trial_crossings positions:
                   both carriageways are split at matching points, the two split nodes joined into
                   one junction, a crossing guessed across it, and a fixed-time plan imposed.
flyover_opened   = trial_crossings network (demand differs; see make_demand.py)
Writes net/<scenario>.net.xml, net/trial_tls.add.xml and out/checks/trial_crossings.csv
"""
import csv, os, shutil
from common import P, cfg, read_net, centrelines, carriageways, M2LL
import netpatch

C = cfg()
os.makedirs(P('net', 'plain'), exist_ok=True)
shutil.copy(P('net', 'base.net.xml'), P('net', 'baseline.net.xml'))

base = read_net(P('net', 'base.net.xml'))
CL, CW = centrelines(), carriageways()
nearest_on = netpatch.nearest_on
edge_at = lambda lonlat, heading_m: netpatch.edge_at(base, lonlat, heading_m)

sites = []
for side, dists in C['trial_crossings'].items():
    if side.startswith('_'): continue
    a, b = side[0], side[1]
    for d in dists:
        (cx, cy), _ = CL[side].at(d)
        ends = []
        for fr, to in ((a, b), (b, a)):
            dist, q, hd = nearest_on(CW[(side, fr, to)], (cx, cy))
            e, pos, off = edge_at(M2LL(q), hd)
            pos = max(8.0, min(e.getLength() - 8.0, pos))           # keep clear of existing nodes
            ends.append((e.getID(), round(pos, 1), fr, to))
        lon, lat = M2LL((cx, cy))
        sites.append(dict(side=side, dist_m=d, lon=round(lon, 6), lat=round(lat, 6), ends=ends))

tls_ids, ok = netpatch.build(P('net', 'base.net.xml'), P('net', 'trial_crossings.net.xml'), sites, P('net', 'trial_tls.add.xml'),
                             'trial', 'xing', 'trial')
shutil.copy(P('net', 'trial_crossings.net.xml'), P('net', 'flyover_opened.net.xml'))

with open(P('out', 'checks', 'trial_crossings.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['side', 'dist_from_first_junction_m', 'lon', 'lat', 'tls_id', 'vehicle_links', 'crossing_links', 'split_edges'])
    for s, tl in zip(sites, tls_ids):
        v = next((x for x in ok if x[0] == tl), (tl, 0, 0))
        w.writerow([s['side'], s['dist_m'], s['lon'], s['lat'], tl, v[1], v[2], ' '.join(f"{e}@{p}" for e, p, _, _ in s['ends'])])
        print(f"{s['side']} {s['dist_m']:4} m  tls={tl[:40]:40} vehicle links {v[1]}  crossing links {v[2]}")
