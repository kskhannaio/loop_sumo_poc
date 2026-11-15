"""Step 5 - metrics for every scenario that has run. Only trips starting 08:00-09:00 count.

Writes out/metrics/*.csv and out/metrics/metrics.json:
  summary.csv          one row per scenario: headline KPIs and sanity checks
  people_by_side.csv   people crossing each loop road: trip time, time lost, walk length, detour
  vehicles_by_side.csv travel time and speed along each loop road, per direction
  queues.csv           queues on the approaches to A, B, C and each trial crossing
  crossings_use.csv    people using each signalised crossing (and other junction crossings)
  buses.csv            bus travel time and delay
"""
import collections, csv, json, math, os, statistics as stt, xml.etree.ElementTree as ET
from common import P, SCENARIOS, SIDES, SIDE_NAME, JUNCTIONS, cfg, hhmm, read_net, carriageways, centrelines, LL2M
import make_demand as MD

C = cfg(); T = C['time']
M0, M1 = hhmm(T['metrics_begin']), hhmm(T['metrics_end'])
os.makedirs(P('out', 'metrics'), exist_ok=True)
meta = {r['id']: r for r in csv.DictReader(open(P('demand', 'person_meta.csv')))}
q = lambda xs, p: (sorted(xs)[min(len(xs) - 1, int(p * len(xs)))] if xs else float('nan'))
mean = lambda xs: (sum(xs) / len(xs) if xs else float('nan'))

def carriageway_edges(net, scn):
    """ordered SUMO edge ids along each loop carriageway (by sampling its geometry every 8 m)."""
    out = {}
    for key, coords in carriageways().items():
        pts = [net.convertLonLat2XY(*c) for c in coords]
        seq = []
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b); n = max(1, int(L // 8))
            for i in range(n):
                x, y = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
                lon, lat = net.convertXY2LonLat(x, y)
                m = MD.map_road(net, (lon, lat), (b[0] - a[0], b[1] - a[1]), 'passenger', 12)
                if m and (not seq or seq[-1] != m[0]): seq.append(m[0])
        out[key] = list(dict.fromkeys(seq))
    return out

rows_sum, rows_ped, rows_veh, rows_q, rows_x, rows_bus = [], [], [], [], [], []
geo = {"type": "FeatureCollection", "features": []}
for scn in SCENARIOS:
    d = P('out', scn)
    if not os.path.exists(os.path.join(d, 'tripinfo.xml')): continue
    net = read_net(P('net', f'{scn}.net.xml'))
    root = ET.parse(os.path.join(d, 'tripinfo.xml')).getroot()
    # ---- people
    ped = collections.defaultdict(list)
    unfinished_people = 0
    for pi in root.findall('personinfo'):
        if not (M0 <= float(pi.get('depart')) < M1): continue
        walks = pi.findall('walk')
        if not walks or any(float(w.get('arrival', -1)) < 0 for w in walks): unfinished_people += 1; continue
        m = meta.get(pi.get('id'))
        if not m: continue
        dur = sum(float(w.get('duration')) for w in walks)
        length = sum(float(w.get('routeLength')) for w in walks)
        loss = sum(float(w.get('timeLoss')) for w in walks)
        ped[(m['kind'], m['side'])].append((dur, loss, length, float(m['straight_m'])))
    for side in SIDES:
        xs = ped[('crossing', side)]
        if not xs: continue
        rows_ped.append({'scenario': scn, 'side': side, 'road': SIDE_NAME[side], 'people': len(xs),
                         'trip_time_mean_s': round(mean([x[0] for x in xs]), 1), 'trip_time_p85_s': round(q([x[0] for x in xs], .85), 1),
                         'time_lost_mean_s': round(mean([x[1] for x in xs]), 1),
                         'walk_m_mean': round(mean([x[2] for x in xs]), 1), 'straight_m_mean': round(mean([x[3] for x in xs]), 1),
                         'detour_factor_median': round(stt.median([x[2] / max(1, x[3]) for x in xs]), 2),
                         'extra_walk_m_mean': round(mean([x[2] - x[3] for x in xs]), 1)})
    allx = [x for (k, s), v in ped.items() if k == 'crossing' for x in v]
    # ---- vehicles and buses
    # vehicles wanting to start 08:00-09:00: delay includes waiting to enter the network (departDelay),
    # because an oversaturated entry otherwise hides congestion
    veh, bus, unfinished_veh, insert_wait = [], [], 0, []
    for ti in root.findall('tripinfo'):
        want = float(ti.get('depart')) - float(ti.get('departDelay', 0))
        if not (M0 <= want < M1): continue
        if float(ti.get('arrival', -1)) < 0: unfinished_veh += 1; continue
        dd = float(ti.get('departDelay', 0))
        rec = (float(ti.get('duration')) + dd, float(ti.get('timeLoss')) + dd, float(ti.get('routeLength')))
        if ti.get('vType') == 'bus': bus.append(rec)
        else: veh.append(rec); insert_wait.append(dd)
    rows_bus.append({'scenario': scn, 'buses': len(bus), 'trip_time_mean_s': round(mean([b[0] for b in bus]), 1),
                     'delay_mean_s': round(mean([b[1] for b in bus]), 1), 'delay_p85_s': round(q([b[1] for b in bus], .85), 1)})
    # ---- travel time along each loop road from edge data
    ed = {}
    for iv in ET.parse(os.path.join(d, 'edgedata.xml')).getroot().findall('interval'):
        for e in iv.findall('edge'): ed[e.get('id')] = e
    # same physical stretch in every scenario: baseline edges, each expanded to its split pieces (E, E.<pos>)
    if 'BASE_CW' not in globals(): BASE_CW = carriageway_edges(read_net(P('net', 'baseline.net.xml')), 'baseline')
    ids = [e.getID() for e in net.getEdges()]
    expand = lambda eid: sorted([i for i in ids if i == eid or i.startswith(eid + '.')],
                                key=lambda i: float(i.split('.', 1)[1]) if i != eid and i.split('.', 1)[1].replace('.', '').isdigit() else -1)
    cw = {k: [x for eid in v for x in expand(eid)] for k, v in BASE_CW.items()}
    for (side, fr, to), edges in cw.items():
        tt = 0.0; L = 0.0; ff = 0.0; entered = []
        for eid in edges:
            e = net.getEdge(eid); L += e.getLength(); ff += e.getLength() / e.getSpeed()
            rec = ed.get(eid)
            tt += float(rec.get('traveltime')) if rec is not None and rec.get('traveltime') else e.getLength() / e.getSpeed()
            if rec is not None and rec.get('entered'): entered.append(float(rec.get('entered')))
            geo['features'].append({"type": "Feature", "properties": {
                "scenario": scn, "side": side, "direction": f"{fr}>{to}", "edge": eid,
                "speed_kmh": round(float(rec.get('speed')) * 3.6, 1) if rec is not None and rec.get('speed') else None,
                "vehicles_per_h": int(float(rec.get('entered'))) if rec is not None and rec.get('entered') else 0,
                "delay_s_per_veh": round(float(rec.get('traveltime')) - e.getLength() / e.getSpeed(), 1) if rec is not None and rec.get('traveltime') else None},
                "geometry": {"type": "LineString", "coordinates": [list(net.convertXY2LonLat(*p)) for p in e.getShape()]}})
        rows_veh.append({'scenario': scn, 'side': side, 'road': SIDE_NAME[side], 'direction': f"{fr}>{to}", 'length_m': round(L),
                         'travel_time_s': round(tt, 1), 'free_flow_s': round(ff, 1), 'delay_s': round(tt - ff, 1),
                         'avg_speed_kmh': round(L / tt * 3.6, 1) if tt else None, 'vehicles_per_h': int(max(entered) if entered else 0)})
    # ---- queues
    qd = collections.defaultdict(list)
    if os.path.exists(os.path.join(d, 'queues.xml')):
        for iv in ET.parse(os.path.join(d, 'queues.xml')).getroot().findall('interval'):
            if float(iv.get('begin')) < M0 or float(iv.get('end')) > M1: continue      # 30-min intervals; keep 08:00-09:00
            label = iv.get('id').split('_')[1]
            qd[label].append((float(iv.get('meanMaxJamLengthInMeters')), float(iv.get('maxJamLengthInMeters'))))
    for label, xs in sorted(qd.items()):
        rows_q.append({'scenario': scn, 'signal': label, 'approach_lanes': len(xs),
                       'mean_queue_m_worst_lane': round(max(x[0] for x in xs), 1), 'max_queue_m': round(max(x[1] for x in xs), 1)})
    # ---- crossing use (people entering crossing edges), grouped by signal
    sig = dict(l.strip().split('\t') for l in open(os.path.join(d, 'signals.txt')))
    by_node = collections.Counter()
    for iv in ET.parse(os.path.join(d, 'edgedata_people.xml')).getroot().findall('interval'):
        for e in iv.findall('edge'):
            eid = e.get('id')
            if eid.startswith(':') and '_c' in eid:
                node = eid[1:eid.rindex('_c')]
                by_node[node] += float(e.get('entered', 0))
    tl_nodes = {}
    for label, tid in sig.items():
        for c in net.getTLS(tid).getConnections(): tl_nodes[c[0].getEdge().getToNode().getID()] = label
    # a junction without a signal (config signals.signalised_junctions) is still A, B or C: label it by position
    jxy = {j: net.convertLonLat2XY(*ll) for j, ll in JUNCTIONS.items()}
    def label_of(node):
        if node in tl_nodes: return tl_nodes[node]
        try: xy = net.getNode(node).getCoord()
        except Exception: return 'other junctions'
        j = min(jxy, key=lambda k: math.dist(jxy[k], xy))
        return j if math.dist(jxy[j], xy) < 60 else 'other junctions'
    agg = collections.Counter()
    for node, n in by_node.items(): agg[label_of(node)] += n
    # foot over bridges: people entering a bridge edge (OSM footway bridges; ids of the joining footways start '-8')
    on_edge = collections.Counter()
    for iv in ET.parse(os.path.join(d, 'edgedata_people.xml')).getroot().findall('interval'):
        for e in iv.findall('edge'): on_edge[e.get('id')] += float(e.get('entered', 0))
    bridges = collections.defaultdict(list)
    for e in net.getEdges():
        if e.getType() == 'highway.footway' and not e.getID().lstrip('-').startswith('8') and len(e.getID().split('#')[0].lstrip('-')) < 11:
            bridges[e.getID().lstrip('-').split('#')[0]].append(e)
    CL = centrelines()
    for way, es in bridges.items():
        n = max(sum(on_edge[x.getID()] for x in es if x.getID().lstrip('-') == k) for k in {x.getID().lstrip('-') for x in es})
        best = None
        for e in es:                                  # where it spans a loop road: side and distance along it
            shp = e.getShape(); mx, my = LL2M(net.convertXY2LonLat(*shp[len(shp) // 2]))
            for side, c in CL.items():
                for i in range(len(c.pts) - 1):
                    (ax, ay), (bx, by) = c.pts[i], c.pts[i + 1]; L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1
                    t = max(0, min(1, ((mx - ax) * (bx - ax) + (my - ay) * (by - ay)) / L2))
                    dd = math.dist((mx, my), (ax + t * (bx - ax), ay + t * (by - ay)))
                    if dd < 25 and (best is None or dd < best[0]): best = (dd, side, c.ch[i] + t * math.sqrt(L2))
        agg[f"FOB {best[1]}@{round(best[2])}" if best else 'foot bridges off the loop'] += n
    for label, n in sorted(agg.items()): rows_x.append({'scenario': scn, 'crossing': label, 'people_per_h': int(n)})
    # ---- sanity
    st = ET.parse(os.path.join(d, 'stats.xml')).getroot()
    rows_sum.append({'scenario': scn,
                     'people_crossing_trips': len(allx), 'ped_trip_time_mean_s': round(mean([x[0] for x in allx]), 1),
                     'ped_time_lost_mean_s': round(mean([x[1] for x in allx]), 1),
                     'ped_detour_factor_median': round(stt.median([x[2] / max(1, x[3]) for x in allx]), 2) if allx else None,
                     'ped_extra_walk_m_mean': round(mean([x[2] - x[3] for x in allx]), 1),
                     'vehicles_finished': len(veh), 'veh_trip_time_mean_s': round(mean([v[0] for v in veh]), 1),
                     'veh_delay_mean_s': round(mean([v[1] for v in veh]), 1),
                     'bus_delay_mean_s': round(mean([b[1] for b in bus]), 1),
                     'veh_insert_wait_mean_s': round(mean(insert_wait), 1),
                     'vehicles_not_inserted': int(st.find('vehicles').get('loaded')) - int(st.find('vehicles').get('inserted')),
                     'unfinished_vehicles': unfinished_veh, 'unfinished_people': unfinished_people,
                     'teleports': int(st.find('teleports').get('total')), 'teleports_jam': int(st.find('teleports').get('jam')),
                     'collisions': int(st.find('safety').get('collisions')) if st.find('safety') is not None else None})
    # crossing points for the map
    if scn == 'trial_crossings':
        for r in csv.DictReader(open(P('out', 'checks', 'trial_crossings.csv'))):
            geo['features'].append({"type": "Feature", "properties": {"scenario": scn, "kind": "trial_crossing", "side": r['side'],
                                    "dist_from_first_junction_m": int(r['dist_from_first_junction_m']), "tls": r['tls_id']},
                                    "geometry": {"type": "Point", "coordinates": [float(r['lon']), float(r['lat'])]}})

def write(name, rows):
    if not rows: return
    with open(P('out', 'metrics', name), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for name, rows in (('summary.csv', rows_sum), ('people_by_side.csv', rows_ped), ('vehicles_by_side.csv', rows_veh),
                   ('queues.csv', rows_q), ('crossings_use.csv', rows_x), ('buses.csv', rows_bus)): write(name, rows)
json.dump({'summary': rows_sum, 'people': rows_ped, 'vehicles': rows_veh, 'queues': rows_q, 'crossings': rows_x, 'buses': rows_bus},
          open(P('out', 'metrics', 'metrics.json'), 'w'), indent=1)
json.dump(geo, open(P('out', 'metrics', 'results.geojson'), 'w'))
for r in rows_sum: print(r)
