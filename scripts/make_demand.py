"""Step 3 - travel demand for the 08:00-09:00 weekday peak (plus warm-up), identical across scenarios.

A scenario-independent spec is generated once from a fixed seed, in lon/lat (demand/spec.json),
then mapped onto each scenario's network, because the trial network splits some edges.

  vehicles   OD flows between gateways (config od_peak_veh_per_hour) with the OD-study vehicle mix,
             plus local random trips; flyover_opened scales the corridor ODs down by divert_share.
  buses      real BMTC trips from inputs/gtfs_peak.json, stopping at mapped bus stops (dwell from config).
  people     (a) trips crossing the loop roads to reach each place people cross to reach (study data)
                 and each bus stop on the loop, (b) background walking. Rates in config.
Writes demand/spec.json, demand/<scenario>/{vehicles,buses,persons}.rou.xml, busstops.add.xml,
and demand/person_meta.csv (id, kind, place, side, straight-line distance).
"""
import collections, csv, json, math, os, random, xml.etree.ElementTree as ET
from common import P, SCENARIOS, SIDES, JUNCTIONS, cfg, hhmm, read_net, load_geo, carriageways, LL2M, M2LL, sumolib, KX, KY

C = cfg()
T = C['time']
B, E, M1 = hhmm(T['sim_begin']), hhmm(T['sim_end']), hhmm(T['metrics_end'])
rng = random.Random(T['seed'])
os.makedirs(P('demand'), exist_ok=True)

# ------------------------------------------------------------------ network lookups
_nets = {}
def net_for(scn):
    if scn not in _nets: _nets[scn] = read_net(P('net', f'{scn}.net.xml'))
    return _nets[scn]

def lane_pos(lane, x, y):
    shp = lane.getShape()
    off = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint((x, y), shp)
    return max(0.5, min(lane.getLength() - 0.5, off * lane.getLength() / max(1e-6, sumolib.geomhelper.polyLength(shp))))

def heading_at(lane, pos):
    shp = lane.getShape(); acc = 0
    for a, b in zip(shp, shp[1:]):
        L = math.dist(a, b)
        if acc + L >= pos * sumolib.geomhelper.polyLength(shp) / lane.getLength(): return (b[0] - a[0], b[1] - a[1])
        acc += L
    a, b = shp[-2], shp[-1]; return (b[0] - a[0], b[1] - a[1])

def map_road(net, lonlat, heading=None, vclass='passenger', r=30):
    """Nearest drivable lane (optionally matching a heading given in metres-space) -> (edge id, lane index, pos)."""
    x, y = net.convertLonLat2XY(*lonlat)
    hx = hy = None
    if heading is not None and math.hypot(*heading) > 0:            # heading in metres (east, north)
        L = math.hypot(*heading)
        x2, y2 = net.convertLonLat2XY(lonlat[0] + heading[0] / L * 5 / KX, lonlat[1] + heading[1] / L * 5 / KY); hx, hy = x2 - x, y2 - y
    best = None
    for lane, d in net.getNeighboringLanes(x, y, r):
        if not lane.allows(vclass) or lane.getEdge().getFunction() not in ('', 'normal'): continue
        pos = lane_pos(lane, x, y)
        if hx is not None:
            ex, ey = heading_at(lane, pos)
            if ex * hx + ey * hy <= 0: continue
        if best is None or d < best[3]: best = (lane.getEdge().getID(), lane.getIndex(), pos, d)
    return best

def map_walk(net, lonlat, r=30):
    """Nearest lane people can walk on -> (edge id, pos)."""
    x, y = net.convertLonLat2XY(*lonlat)
    best = None
    for lane, d in net.getNeighboringLanes(x, y, r):
        if not lane.allows('pedestrian') or lane.getEdge().getFunction() not in ('', 'normal'): continue
        pref = 0 if not lane.allows('passenger') else 8            # prefer real sidewalks
        if best is None or d + pref < best[2]: best = (lane.getEdge().getID(), lane_pos(lane, x, y), d + pref)
    return best

# ------------------------------------------------------------------ spec (scenario-independent)
def build_spec():
    base = net_for('baseline')
    spec = {"buses": [], "persons": [], "local": []}
    # local vehicle trips between minor-road edges (not the loop's main roads)
    minor = [e for e in base.getEdges() if e.allows('passenger') and e.getPriority() < 11 and e.getLength() > 30]
    n_local = int(C['od_peak_veh_per_hour']['local_random'] * (E - B) / 3600)
    for i in range(n_local):
        while True:
            a, b = rng.choice(minor), rng.choice(minor)
            if a is not b and math.dist(a.getFromNode().getCoord(), b.getToNode().getCoord()) > 300 \
                    and base.getShortestPath(a, b, vClass='passenger')[0]: break
        ends = []
        for e in (a, b):
            shp = e.getShape(); mx, my = shp[len(shp) // 2] if len(shp) > 2 else ((shp[0][0] + shp[-1][0]) / 2, (shp[0][1] + shp[-1][1]) / 2)
            lon, lat = base.convertXY2LonLat(mx, my)
            dx, dy = shp[-1][0] - shp[0][0], shp[-1][1] - shp[0][1]
            ends.append([lon, lat, dx, dy])
        spec['local'].append({"depart": round(rng.uniform(B, E), 1), "from": ends[0], "to": ends[1]})

    # buses
    for t in json.load(open(P('inputs', 'gtfs_peak.json')))['trips']:
        path = [LL2M(c) for c in t['path']]
        dist = [0.0]
        for a, b in zip(path, path[1:]): dist.append(dist[-1] + math.dist(a, b))
        if not t['calls'] or dist[-1] < 80: continue
        # depart at the entry point, timed so the bus reaches its first stop at the timetabled time (~7 m/s)
        first = LL2M([t['calls'][0]['lon'], t['calls'][0]['lat']])
        k = min(range(len(path)), key=lambda i: math.dist(path[i], first))
        depart = t['calls'][0]['t'] - dist[k] / 7.0
        if not (B <= depart < E): continue
        hd = lambda i: (path[min(i + 1, len(path) - 1)][0] - path[max(i - 1, 0)][0], path[min(i + 1, len(path) - 1)][1] - path[max(i - 1, 0)][1])
        stops = []
        for c in t['calls']:
            q = LL2M([c['lon'], c['lat']]); j = min(range(len(path)), key=lambda i: math.dist(path[i], q))
            stops.append({"name": c['name'], "lonlat": [c['lon'], c['lat']], "heading": list(hd(j))})
        spec['buses'].append({"id": f"bus_{t['route']}_{t['trip']}".replace(' ', '').replace(':', '_'), "route": t['route'], "depart": round(depart, 1),
                              "from": t['path'][0] + list(hd(0)), "to": t['path'][-1] + list(hd(len(path) - 1)),
                              "stops": stops})

    # people crossing the loop roads to reach places
    ped = C['pedestrians']; rates = ped['crossing_trips_per_hour_by_type']
    CW = carriageways()
    def nearest(coords, p):
        best = (1e18, None, None)
        pts = [LL2M(c) for c in coords]
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
            t_ = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2)) if L2 else 0
            q = (a[0] + t_ * dx, a[1] + t_ * dy)
            if math.dist(p, q) < best[0]: best = (math.dist(p, q), q, (dx, dy))
        return best
    def along(coords, q, offset):
        """point `offset` metres along the carriageway from its nearest point to q."""
        pts = [LL2M(c) for c in coords]
        acc, base_d = 0.0, None
        dists = [0.0]
        for a, b in zip(pts, pts[1:]): dists.append(dists[-1] + math.dist(a, b))
        _, foot, _ = nearest(coords, q)
        i0 = min(range(len(pts) - 1), key=lambda i: abs(math.dist(pts[i], foot) + math.dist(foot, pts[i + 1]) - math.dist(pts[i], pts[i + 1])))
        d0 = dists[i0] + math.dist(pts[i0], foot); d = max(5.0, min(dists[-1] - 5.0, d0 + offset))
        for i in range(len(pts) - 1):
            if dists[i] <= d <= dists[i + 1]:
                t_ = (d - dists[i]) / ((dists[i + 1] - dists[i]) or 1); a, b = pts[i], pts[i + 1]
                return (a[0] + t_ * (b[0] - a[0]), a[1] + t_ * (b[1] - a[1])), ((b[0] - a[0]), (b[1] - a[1]))
        return pts[-1], (1, 0)
    def kerb(p, dvec, other):
        """step 4 m from the carriageway line away from the opposite carriageway (onto the footpath)."""
        L = math.hypot(*dvec) or 1; nx, ny = -dvec[1] / L, dvec[0] / L
        if (other[0] - p[0]) * nx + (other[1] - p[1]) * ny > 0: nx, ny = -nx, -ny
        return (p[0] + nx * 4, p[1] + ny * 4)

    places = []
    for f in load_geo('crossings.geojson'):
        p = f['properties']
        if p['kind'] == 'generator' and p['type'] != 'Bus stop' and rates.get(p['type']):
            places.append((p['name'], p['type'], p['side'], f['geometry']['coordinates'], rates[p['type']]))
    for f in load_geo('bus_stops.geojson'):
        p = f['properties']
        if p['on_loop'] and p['timetabled']:
            places.append((p['name'] + ' bus stop', 'Bus stop', p['side'], f['geometry']['coordinates'],
                           p['buses_peak'] * ped['pax_per_bus_board_alight'] * ped['share_of_bus_pax_crossing_the_road']))
    for name, kind, side, ll, rate in places:
        a, b = side[0], side[1]
        g = LL2M(ll)
        d1, q1, v1 = nearest(CW[(side, a, b)], g); d2, q2, v2 = nearest(CW[(side, b, a)], g)
        near, far = ((side, a, b), (side, b, a)) if d1 <= d2 else ((side, b, a), (side, a, b))
        qn = q1 if d1 <= d2 else q2; qf = q2 if d1 <= d2 else q1
        n = max(0, round(rate * (M1 - B) / 3600 * (1 + rng.uniform(-0.05, 0.05))))
        for i in range(n):
            off = rng.uniform(*ped['origin_offset_m'])
            fp, fv = along(CW[far], g, off)
            np_, nv = along(CW[near], g, 0)
            o = kerb(fp, fv, qn); dst = kerb(np_, nv, qf)
            if rng.random() < 0.5: o, dst = dst, o                       # half go to the place, half leave it
            spec['persons'].append({"kind": "crossing", "place": name, "type": kind, "side": side,
                                    "depart": round(rng.uniform(B, M1), 1), "from": list(M2LL(o)), "to": list(M2LL(dst)),
                                    "straight_m": round(math.dist(o, dst), 1)})
    # background walking on any footpath in the area
    walk_lanes = [l for e in base.getEdges() for l in e.getLanes() if l.allows('pedestrian') and not l.allows('passenger')]
    for i in range(int(ped['background_walk_trips_per_hour'] * (M1 - B) / 3600)):
        while True:
            la, lb = rng.choice(walk_lanes), rng.choice(walk_lanes)
            pa = la.getShape()[0]; pb = lb.getShape()[-1]
            if 150 <= math.dist(pa, pb) <= 600: break
        spec['persons'].append({"kind": "background", "place": "", "type": "", "side": "", "depart": round(rng.uniform(B, M1), 1),
                                "from": list(base.convertXY2LonLat(*pa)), "to": list(base.convertXY2LonLat(*pb)),
                                "straight_m": round(math.dist(pa, pb), 1)})
    spec['persons'].sort(key=lambda p: p['depart'])
    for i, p in enumerate(spec['persons']): p['id'] = f"p{i:05d}_{p['kind'][:4]}"
    json.dump(spec, open(P('demand', 'spec.json'), 'w'))
    with open(P('demand', 'person_meta.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['id', 'kind', 'place', 'type', 'side', 'depart', 'straight_m'])
        for p in spec['persons']: w.writerow([p['id'], p['kind'], p['place'], p['type'], p['side'], p['depart'], p['straight_m']])
    return spec

# ------------------------------------------------------------------ per-scenario files
VT = {  # vehicle types: sublane model lets two-wheelers filter between cars
    'two_wheeler': dict(color='255,140,0', vClass='motorcycle', length='2.0', width='0.8', minGap='1.0', accel='2.6', decel='6.0', maxSpeed='16.7',
                        sigma='0.6', speedFactor='normc(1.05,0.12,0.8,1.3)', latAlignment='arbitrary', minGapLat='0.3',
                        lcSublane='5', lcPushy='0.6', lcAssertive='1.5', guiShape='motorcycle'),
    'car':        dict(color='52,98,186', vClass='passenger', length='4.3', width='1.8', minGap='2.0', accel='2.2', decel='4.5', sigma='0.5',
                        speedFactor='normc(1.0,0.1,0.8,1.2)', minGapLat='0.6', lcSublane='2', guiShape='passenger'),
    'van_maxicab': dict(color='90,150,220', vClass='passenger', length='5.0', width='1.9', minGap='2.0', accel='1.8', decel='4.5', sigma='0.5',
                        minGapLat='0.6', guiShape='passenger/van'),
    'auto':       dict(color='40,170,70', vClass='passenger', length='3.2', width='1.4', minGap='1.5', accel='1.6', decel='4.0', maxSpeed='13.9',
                        sigma='0.6', minGapLat='0.4', lcSublane='3', latAlignment='arbitrary', guiShape='passenger/hatchback'),
    'goods_auto': dict(color='150,110,60', vClass='delivery', length='3.5', width='1.5', minGap='1.5', accel='1.3', decel='4.0', maxSpeed='12.5',
                        minGapLat='0.4', guiShape='delivery'),
    'lcv':        dict(color='150,110,60', vClass='delivery', length='5.5', width='2.0', minGap='2.0', accel='1.4', decel='4.0', guiShape='delivery'),
    'truck':      dict(color='110,70,40', vClass='truck', length='9.0', width='2.5', minGap='2.5', accel='1.0', decel='4.0', guiShape='truck'),
}

def gateways(net):
    road = lambda e: e.allows('passenger') and e.getFunction() in ('', 'normal')
    entries = [e for e in net.getEdges() if road(e) and not [i for i in e.getFromNode().getIncoming() if road(i) and i.getFromNode() is not e.getToNode()]]
    exits = [e for e in net.getEdges() if road(e) and not [o for o in e.getToNode().getOutgoing() if road(o) and o.getToNode() is not e.getFromNode()]]
    # gateway anchors (lon/lat), separate for traffic entering and leaving, picked from the OSM extract:
    # HN Hosur Rd north; HS Hosur Rd south (the extract ends where southbound Hosur Rd meets Madiwala-Sarjapura Rd);
    # SE Sarjapura Rd east of A; IRR 100 Ft / Inner Ring Rd north-east of A; TW Tavarekere Main Rd west of C (exit only).
    ANCHORS = {'HN': ((77.61241, 12.93437), (77.61233, 12.93427)), 'HS': ((77.62011, 12.92127), (77.62030, 12.92121)),
               'SE': ((77.62515, 12.92570), (77.62828, 12.92450)), 'IRR': ((77.62449, 12.93519), (77.62441, 12.93527)),
               'TW': (None, (77.61280, 12.93025))}           # Tavarekere Main Rd is one-way westbound: exit only
    roads = [e for e in net.getEdges() if road(e) and e.getPriority() >= 10 and e.getOutgoing() is not None]
    gw = {}
    for g, (a_in, a_out) in ANCHORS.items():
        xi, yi = net.convertLonLat2XY(*a_in) if a_in else (1e12, 1e12); xo, yo = net.convertLonLat2XY(*a_out)
        ins = [e for e in roads if [o for o in e.getOutgoing() if road(o)]]          # must lead somewhere
        outs = [e for e in roads if [i for i in e.getIncoming() if road(i)]]         # must be reachable
        a = min(ins, key=lambda e: math.dist(e.getFromNode().getCoord(), (xi, yi)))
        b = min(outs, key=lambda e: math.dist(e.getToNode().getCoord(), (xo, yo)))
        gw[g] = (a if math.dist(a.getFromNode().getCoord(), (xi, yi)) < 60 else None,
                 b if math.dist(b.getToNode().getCoord(), (xo, yo)) < 60 else None)
    return gw

def write_scenario(scn, spec):
    net = net_for(scn)
    d = P('demand', scn); os.makedirs(d, exist_ok=True)
    gw = gateways(net)
    report = [f"gateway {g}: in={a.getID() if a else None} out={b.getID() if b else None}" for g, (a, b) in gw.items()]
    # vehicles
    root = ET.Element('routes')
    mix = {k: v for k, v in C['vehicle_mix'].items() if not k.startswith('_')}
    tot = sum(mix.values())
    for k, attrs in VT.items(): ET.SubElement(root, 'vType', id=k, **attrs)
    dist = ET.SubElement(root, 'vTypeDistribution', id='mix')
    dist.set('vTypes', ' '.join(mix)); dist.set('probabilities', ' '.join(f"{mix[k] / tot:.4f}" for k in mix))
    ET.SubElement(root, 'vType', id='bus', vClass='bus', length='12', width='2.6', minGap='2.5', accel='1.0', decel='4.0',
                  minGapLat='0.8', lcStrategic='3', lcPushy='0.5', lcAssertive='2', guiShape='bus', color='215,30,40')
    ET.SubElement(root, 'vType', id='walker', vClass='pedestrian', speed=str(C['pedestrians']['walking_speed_mps']), color='200,0,200')
    fly = C['flyover_opened']
    for od, vph in C['od_peak_veh_per_hour'].items():
        if od.startswith('_') or od == 'local_random': continue
        o, dst = od.split('>')
        if scn == 'flyover_opened' and od in fly['applies_to']: vph = vph * (1 - fly['divert_share'])
        a, b = gw[o][0], gw[dst][1]
        if not a or not b or vph <= 0: report.append(f"  skipped OD {od}"); continue
        ET.SubElement(root, 'flow', id=f"od_{o}_{dst}", type='mix', begin=str(B), end=str(E), period=f"exp({vph / 3600:.5f})",
                      attrib={'from': a.getID(), 'to': b.getID(), 'departLane': 'best', 'departSpeed': 'max', 'departPos': 'base'})
    flows = list(root)
    vehicles = []
    for i, t in enumerate(spec['local']):
        a = map_road(net, t['from'][:2], t['from'][2:]); b = map_road(net, t['to'][:2], t['to'][2:])
        if a and b and a[0] != b[0]:
            vehicles.append((t['depart'], ET.Element('trip', id=f"local{i}", type='mix', depart=str(t['depart']),
                             attrib={'from': a[0], 'to': b[0], 'departLane': 'best', 'departSpeed': 'max'})))
    vehicles.sort(key=lambda v: v[0])
    for _, el in vehicles: root.append(el)
    ET.ElementTree(root).write(os.path.join(d, 'vehicles.rou.xml'))

    # buses + their stops
    stops_add, stop_ids = ET.Element('additional'), {}
    broot = ET.Element('routes'); nb = 0
    for b in sorted(spec['buses'], key=lambda b: b['depart']):          # SUMO needs route files sorted by depart
        fa = map_road(net, b['from'][:2], b['from'][2:], 'bus', 40); ta = map_road(net, b['to'][:2], b['to'][2:], 'bus', 40)
        if not fa or not ta: continue
        el = ET.Element('trip', id=b['id'], type='bus', depart=str(b['depart']), attrib={'from': fa[0], 'to': ta[0], 'departLane': 'best'})
        for s in b['stops']:
            m = map_road(net, s['lonlat'], s['heading'], 'bus', 40)
            if not m: continue
            # stop on the bus lane that leads to the most onward edges (kerb lane on ties), so a bus that has
            # stopped can still continue straight or turn without an impossible lane change
            edge = net.getEdge(m[0])
            reach = lambda l: len({c.getTo().getID() for c in l.getOutgoing()}) if hasattr(l, 'getOutgoing') else 0
            cands = [l for l in edge.getLanes() if l.allows('bus') and not (l.allows('pedestrian') and not l.allows('passenger'))]
            li = max(cands, key=lambda l: (reach(l), -l.getIndex())).getIndex() if cands else m[1]
            L = net.getEdge(m[0]).getLength()
            # a 40 m stop (room for ~3 buses), ending at least 50 m before the edge end so buses can still change
            # lanes for their next turn (GTFS stop positions are approximate, so shifting upstream is acceptable)
            end = min(m[2] + 20, L - 50) if L > 95 else L - 1
            start = max(0.0, end - 40)
            key = (m[0], li, round(end / 10))
            if key not in stop_ids:
                sid = f"bs_{len(stop_ids)}"
                stop_ids[key] = sid
                ET.SubElement(stops_add, 'busStop', id=sid, lane=f"{m[0]}_{li}", startPos=f"{start:.1f}",
                              endPos=f"{max(end, start + 10):.1f}", name=s['name'], friendlyPos='true')
            ET.SubElement(el, 'stop', busStop=stop_ids[key], duration=str(C['buses']['dwell_s']))
        broot.append(el); nb += 1
    ET.ElementTree(stops_add).write(os.path.join(d, 'busstops.add.xml'))
    ET.ElementTree(broot).write(os.path.join(d, 'buses.rou.xml'))

    # people
    proot = ET.Element('routes'); npers = 0; unmapped = 0
    for p in spec['persons']:
        a = map_walk(net, p['from']); b = map_walk(net, p['to'])
        if not a or not b or (a[0] == b[0] and abs(a[1] - b[1]) < 5): unmapped += 1; continue
        pe = ET.SubElement(proot, 'person', id=p['id'], depart=str(p['depart']), departPos=f"{a[1]:.1f}", type='walker')
        ET.SubElement(pe, 'personTrip', attrib={'from': a[0], 'to': b[0], 'arrivalPos': f"{b[1]:.1f}"})
        npers += 1
    ET.ElementTree(proot).write(os.path.join(d, 'persons.rou.xml'))
    report.append(f"{scn}: OD flows {len(flows) - len(VT) - 4}, local trips {len(vehicles)}, buses {nb} (of {len(spec['buses'])}), "
                  f"bus stops {len(stop_ids)}, people {npers} (unmapped {unmapped})")
    return report

if __name__ == '__main__':
    spec = build_spec()
    print(f"spec: {len(spec['local'])} local trips, {len(spec['buses'])} buses, {len(spec['persons'])} people "
          f"({sum(1 for p in spec['persons'] if p['kind'] == 'crossing')} crossing the loop roads)")
    lines = []
    for scn in SCENARIOS: lines += write_scenario(scn, spec)
    open(P('out', 'checks', 'demand_checks.txt'), 'w').write('\n'.join(lines))
    print('\n'.join(lines))
