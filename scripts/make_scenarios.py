"""Step 2 - scenario networks.

baseline         = net/base.net.xml (crossings only where netconvert guessed them at junctions)
trial_crossings  = base + signalised mid-block crossings at config trial_crossings positions:
                   both carriageways are split at matching points, the two split nodes joined into
                   one junction, a crossing guessed across it, and a fixed-time plan imposed.
flyover_opened   = trial_crossings network (demand differs; see make_demand.py)
Writes net/<scenario>.net.xml, net/trial_tls.add.xml and out/checks/trial_crossings.csv
"""
import collections, csv, math, os, re, shutil, xml.etree.ElementTree as ET
from common import BIN, P, SUMO_HOME, cfg, run, read_net, centrelines, carriageways, LL2M, M2LL, sumolib

C = cfg()
os.makedirs(P('net', 'plain'), exist_ok=True)
shutil.copy(P('net', 'base.net.xml'), P('net', 'baseline.net.xml'))

base = read_net(P('net', 'base.net.xml'))
CL, CW = centrelines(), carriageways()

def nearest_on(coords, p):
    best = (1e18, None)
    pts = [LL2M(c) for c in coords]
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2)) if L2 else 0
        q = (a[0] + t * dx, a[1] + t * dy)
        if math.dist(p, q) < best[0]: best = (math.dist(p, q), q, (dx, dy))
    return best

def edge_at(lonlat, heading_m):
    """Road edge under a point whose direction matches the carriageway; returns (edge, pos along edge)."""
    x, y = base.convertLonLat2XY(*lonlat)
    best = None
    for lane, d in base.getNeighboringLanes(x, y, 25):
        e = lane.getEdge()
        if not e.allows('passenger') or d > 25: continue
        shp = e.getShape(); off = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint((x, y), shp)
        i = max(1, min(len(shp) - 1, next((k for k in range(1, len(shp)) if sumolib.geomhelper.polyLength(shp[:k + 1]) >= off), len(shp) - 1)))
        ex, ey = shp[i][0] - shp[i - 1][0], shp[i][1] - shp[i - 1][1]
        if ex * heading_m[0] + ey * heading_m[1] <= 0: continue
        if best is None or d < best[2]:
            best = (e, off * e.getLength() / max(1e-6, sumolib.geomhelper.polyLength(shp)), d)
    return best

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

# ---- patch the base network: splits first, then joins ------------------------------------------
splits = collections.defaultdict(list)
for k, s in enumerate(sites):
    s['nodes'] = []
    for j, (eid, pos, fr, to) in enumerate(s['ends']):
        nid = f"xing{k}_{'ab'[j]}"
        splits[eid].append((pos, nid)); s['nodes'].append(nid)
patch = ET.Element('edges')
for eid, items in splits.items():
    el = ET.SubElement(patch, 'edge', id=eid)
    for pos, nid in sorted(items):
        ET.SubElement(el, 'split', pos=str(pos), id=nid)
ET.ElementTree(patch).write(P('net', 'plain', 'trial_splits.edg.xml'))
joins = ET.Element('nodes')
for s in sites:
    ET.SubElement(joins, 'join', nodes=' '.join(s['nodes']))
ET.ElementTree(joins).write(P('net', 'plain', 'trial_joins.nod.xml'))

tls_ids = ['cluster_' + '_'.join(sorted(s['nodes'])) for s in sites]
M = C['signals']
# pass A: split both carriageways at each site (netconvert remaps connections itself)
run([BIN('netconvert'), '-s', P('net', 'base.net.xml'), '--edge-files', P('net', 'plain', 'trial_splits.edg.xml'),
     '--lefthand', 'true', '--walkingareas', 'true', '--output.street-names', 'true', '--no-warnings', 'true',
     '--output-file', P('net', 'plain', 'split.net.xml')], log=P('out', 'checks', 'netconvert_trial_split.log'))
# Splitting renames the edge piece next to a junction (E -> E.<pos>), and netconvert then drops every junction
# crossing that referenced E (this removed most crossings at A and C). Re-declare them with remapped edge ids.
def crossings_of(path):
    r = ET.parse(path).getroot(); out = {}
    for e in r.findall('edge'):
        if e.get('function') == 'crossing':
            node = e.get('id')[1:e.get('id').rindex('_c')]
            out.setdefault(node, []).append((tuple(e.get('crossingEdges').split()), e.find('lane').get('width')))
    return out
before, after = crossings_of(P('net', 'base.net.xml')), crossings_of(P('net', 'plain', 'split.net.xml'))
split_net = read_net(P('net', 'plain', 'split.net.xml'))
def remap(eid, node):
    if split_net.hasEdge(eid):
        e = split_net.getEdge(eid)
        if node in (e.getFromNode().getID(), e.getToNode().getID()): return eid
    for e in split_net.getNode(node).getIncoming() + split_net.getNode(node).getOutgoing():
        if e.getID().split('.')[0] == eid.split('.')[0] and e.getID().startswith(eid): return e.getID()
    return None
restore = ET.Element('connections'); n_restored = 0
for node, xs in before.items():
    if not split_net.hasNode(node): continue
    have = {tuple(sorted(c)) for c, _ in after.get(node, [])}
    for edges, width in xs:
        new = [remap(e, node) for e in edges]
        if None in new or tuple(sorted(new)) in have: continue
        ET.SubElement(restore, 'crossing', node=node, edges=' '.join(new), width=width); n_restored += 1
ET.ElementTree(restore).write(P('net', 'plain', 'restore_crossings.con.xml'))
print(f'restored {n_restored} junction crossings lost by splitting')

# pass B: join each pair of split nodes into one junction, signalise it, guess its crossing
run([BIN('netconvert'), '-s', P('net', 'plain', 'split.net.xml'), '--node-files', P('net', 'plain', 'trial_joins.nod.xml'),
     '--connection-files', P('net', 'plain', 'restore_crossings.con.xml'),
     '--lefthand', 'true', '--crossings.guess', 'true', '--crossings.guess.speed-threshold', '20', '--walkingareas', 'true',
     '--no-turnarounds', 'true',
     '--tls.set', ','.join(tls_ids), '--tls.default-type', 'static', '--tls.cycle.time', str(M['midblock_cycle_s']),
     '--output.street-names', 'true', '--no-warnings', 'true',
     '--output-file', P('net', 'trial_crossings.net.xml')], log=P('out', 'checks', 'netconvert_trial.log'))
shutil.copy(P('net', 'trial_crossings.net.xml'), P('net', 'flyover_opened.net.xml'))

# ---- fixed pedestrian-friendly plan for each new crossing --------------------------------------
root = ET.parse(P('net', 'trial_crossings.net.xml')).getroot()
fn = {e.get('id'): e.get('function') for e in root.findall('edge')}
links = collections.defaultdict(dict)                  # tls -> linkIndex -> 'veh' | 'ped'
for c in root.findall('connection'):
    tl = c.get('tl')
    if tl in tls_ids:
        kind = 'ped' if fn.get(c.get('to')) == 'crossing' or fn.get(c.get('from')) == 'crossing' else 'veh'
        links[tl][int(c.get('linkIndex'))] = kind
add = ET.Element('additional')
ok = []
for tl, lk in links.items():
    n = max(lk) + 1
    st = lambda v, p: ''.join(v if lk.get(i) == 'veh' else p for i in range(n))
    veh_green = M['midblock_cycle_s'] - M['midblock_ped_green_s'] - M['midblock_yellow_s'] - 4
    prog = ET.SubElement(add, 'tlLogic', id=tl, type='static', programID='trial', offset='0')
    for dur, s in ((veh_green, st('G', 'r')), (M['midblock_yellow_s'], st('y', 'r')), (2, st('r', 'r')),
                   (M['midblock_ped_green_s'], st('r', 'G')), (2, st('r', 'r'))):
        ET.SubElement(prog, 'phase', duration=str(dur), state=s)
    ok.append((tl, sum(1 for v in lk.values() if v == 'veh'), sum(1 for v in lk.values() if v == 'ped')))
ET.ElementTree(add).write(P('net', 'trial_tls.add.xml'))

with open(P('out', 'checks', 'trial_crossings.csv'), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['side', 'dist_from_first_junction_m', 'lon', 'lat', 'tls_id', 'vehicle_links', 'crossing_links', 'split_edges'])
    for s, tl in zip(sites, tls_ids):
        v = next((x for x in ok if x[0] == tl), (tl, 0, 0))
        w.writerow([s['side'], s['dist_m'], s['lon'], s['lat'], tl, v[1], v[2], ' '.join(f"{e}@{p}" for e, p, _, _ in s['ends'])])
        print(f"{s['side']} {s['dist_m']:4} m  tls={tl[:40]:40} vehicle links {v[1]}  crossing links {v[2]}")
missing = [tl for tl in tls_ids if tl not in links]
if missing: raise SystemExit(f'trial crossings not built: {missing}')

# guard: the trial network must keep every baseline crossing (it only adds new ones)
n_base = sum(len(v) for v in crossings_of(P('net', 'base.net.xml')).values())
n_trial = sum(len(v) for v in crossings_of(P('net', 'trial_crossings.net.xml')).values())
n_new = sum(len(v) for k, v in crossings_of(P('net', 'trial_crossings.net.xml')).items() if k.startswith('cluster_xing'))
print(f'crossings: baseline {n_base}, trial {n_trial} ({n_new} new)')
if n_trial - n_new < n_base: raise SystemExit(f'trial network lost {n_base - (n_trial - n_new)} baseline crossings')
