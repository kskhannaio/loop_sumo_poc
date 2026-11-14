"""Step 0 - extract the bus trips we need from the BMTC GTFS into inputs/gtfs_peak.json.

Keeps Monday-service trips that pass through the network area during the simulated window, with
their stops (inside the area) and the path (shape points inside the area). Only re-run when the
GTFS feed changes: `python scripts/prep_gtfs.py [path/to/gtfs]` (default path in assumptions.json).
Source: unofficial BMTC GTFS by Vonter (https://github.com/Vonter/bmtc-gtfs), ODbL.
"""
import csv, json, os, sys
from common import P, cfg, hhmm

C = cfg()
G = sys.argv[1] if len(sys.argv) > 1 else C['buses']['gtfs_dir_default']
if not os.path.exists(os.path.join(G, 'stop_times.txt')):
    raise SystemExit(f'GTFS not found at {G} - download https://github.com/Vonter/bmtc-gtfs/raw/refs/heads/main/gtfs/bmtc.zip, unzip, pass the folder')

# network area (lon/lat) from the OSM extract used for the network, minus a small margin
BOX = (77.6122, 12.9222, 77.6238, 12.9323)
inside = lambda lon, lat: BOX[0] <= lon <= BOX[2] and BOX[1] <= lat <= BOX[3]
t0 = hhmm(C['time']['sim_begin']) - 15 * 60
t1 = hhmm(C['time']['sim_end']) + 15 * 60
sec = lambda s: int(s[:2]) * 3600 + int(s[3:5]) * 60 + int(s[6:8])

cal = {r['service_id']: r for r in csv.DictReader(open(os.path.join(G, 'calendar.txt')))}
routes = {r['route_id']: r for r in csv.DictReader(open(os.path.join(G, 'routes.txt')))}
trips = {r['trip_id']: r for r in csv.DictReader(open(os.path.join(G, 'trips.txt'))) if cal[r['service_id']]['monday'] == '1'}
stops = {r['stop_id']: (float(r['stop_lon']), float(r['stop_lat']), r['stop_name'])
         for r in csv.DictReader(open(os.path.join(G, 'stops.txt')))}
area_stops = {k for k, (lon, lat, _) in stops.items() if inside(lon, lat)}

calls = {}
for r in csv.DictReader(open(os.path.join(G, 'stop_times.txt'))):
    if r['stop_id'] in area_stops and r['trip_id'] in trips:
        t = sec(r['arrival_time'])
        if t0 <= t <= t1: calls.setdefault(r['trip_id'], []).append((int(r['stop_sequence']), t, r['stop_id']))
need_shapes = {trips[t]['shape_id'] for t in calls}
shapes = {}
for r in csv.DictReader(open(os.path.join(G, 'shapes.txt'))):
    if r['shape_id'] in need_shapes:
        shapes.setdefault(r['shape_id'], []).append((int(r['shape_pt_sequence']), float(r['shape_pt_lon']), float(r['shape_pt_lat'])))

out = []
for tid, cs in calls.items():
    cs.sort(); tr = trips[tid]
    pts = [(lon, lat) for _, lon, lat in sorted(shapes.get(tr['shape_id'], []))]
    # the contiguous stretch of the path inside the area that contains the first in-area stop
    idx = [i for i, p in enumerate(pts) if inside(*p)]
    if len(idx) < 2: continue
    runs, cur = [], [idx[0]]
    for i in idx[1:]:
        if i == cur[-1] + 1: cur.append(i)
        else: runs.append(cur); cur = [i]
    runs.append(cur)
    run_pts = max(runs, key=len)
    out.append({"trip": tid, "route": routes[tr['route_id']]['route_short_name'], "headsign": tr['trip_headsign'],
                "path": [list(pts[i]) for i in run_pts],
                "calls": [{"stop": s, "name": stops[s][2], "lon": stops[s][0], "lat": stops[s][1], "t": t} for _, t, s in cs]})
json.dump({"source": "BMTC GTFS by Vonter (ODbL), Monday service", "trips": out}, open(P('inputs', 'gtfs_peak.json'), 'w'))
print(f"bus trips through the area {len(out)} (calls at {len(area_stops)} area stops); saved inputs/gtfs_peak.json "
      f"({os.path.getsize(P('inputs', 'gtfs_peak.json')) // 1024} KB)")
