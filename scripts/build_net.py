"""Step 1 - build the base network from OSM and check it.

Pass 1: OSM -> network (left-hand traffic, layer-separated underpass/flyover, urban speeds,
        sidewalks and junction crossings guessed).
Pass 2: signals at junctions B and C (OSM marks them, pass 1 leaves them unsignalised), joined per
        junction, fixed-time plans from config/assumptions.json.
Writes net/base.net.xml and out/checks/network_checks.txt.
"""
import collections, math, os, xml.etree.ElementTree as ET
from common import BIN, P, SUMO_HOME, JUNCTIONS, SIDES, cfg, run, read_net, carriageways, LL2M, KX, KY

C = cfg()['signals']
N = cfg().get('network', {})
os.makedirs(P('out', 'checks'), exist_ok=True)
os.makedirs(P('net', 'plain'), exist_ok=True)

# ---- corrections to the OSM extract (config "network"), written to a patched copy ----------------
osm = ET.parse(P('osm', 'loop.osm.xml')); osm_root = osm.getroot()
osm_nodes = {n.get('id'): n for n in osm_root.findall('node')}
patched = []
for way in osm_root.findall('way'):
    wid = way.get('id')
    lanes = N.get('lane_overrides', {}).get(wid)
    if lanes:
        for t in way.findall('tag'):
            if t.get('k') == 'lanes': way.remove(t)
        ET.SubElement(way, 'tag', k='lanes', v=str(lanes)); patched.append(f"way {wid}: lanes={lanes}")
    ext = N.get('entrance_extensions', {}).get(wid)
    if ext:                                   # add a node `ext` metres before the first node, on the same bearing
        nds = way.findall('nd')
        a, b = osm_nodes[nds[0].get('ref')], osm_nodes[nds[1].get('ref')]
        ax, ay = float(a.get('lon')) * KX, float(a.get('lat')) * KY
        bx, by = float(b.get('lon')) * KX, float(b.get('lat')) * KY
        L = math.dist((ax, ay), (bx, by))
        nx_, ny_ = ax - (bx - ax) / L * ext, ay - (by - ay) / L * ext
        nid = f"-{wid}"                       # negative ids are free in OSM extracts
        node = ET.Element('node', id=nid, lat=f"{ny_ / KY:.7f}", lon=f"{nx_ / KX:.7f}", version='1')
        osm_root.insert(list(osm_root).index(a), node)
        osm_nodes[nid] = node
        way.insert(list(way).index(nds[0]), ET.Element('nd', ref=nid))
        patched.append(f"way {wid}: entrance extended {ext} m to {ny_ / KY:.5f},{nx_ / KX:.5f}")
# foot over bridges: OSM maps them and their stairs, but not joined to the roads. Each stair foot is joined to the
# nearest surface carriageway with a short footway, so people in the model can reach the bridge from the footpath.
FB = N.get('foot_over_bridges', {})
if FB.get('include'):
    fb = ET.parse(P('osm', 'footbridges.osm.xml')).getroot()
    fnodes = {n.get('id'): n for n in fb.findall('node')}
    fways = {w.get('id'): w for w in fb.findall('way')}
    refs = {wid: [nd.get('ref') for nd in w.findall('nd')] for wid, w in fways.items()}
    tag = lambda w, k: next((t.get('v') for t in w.findall('tag') if t.get('k') == k), None)
    # connected groups of bridge + stairs; keep the groups that contain a bridge
    group = {wid: wid for wid in fways}
    def find(a):
        while group[a] != a: a = group[a]
        return a
    for a in fways:
        for b in fways:
            if a < b and set(refs[a]) & set(refs[b]): group[find(a)] = find(b)
    keep = {find(wid) for wid, w in fways.items() if tag(w, 'bridge') and tag(w, 'highway') == 'footway'}
    kept = [wid for wid in fways if find(wid) in keep]
    count = collections.Counter(r for wid in kept for r in refs[wid])
    xy = lambda n: (float(n.get('lon')) * KX, float(n.get('lat')) * KY)
    surface = [w for w in osm_root.findall('way') if tag(w, 'layer') in (None, '0') and not tag(w, 'tunnel') and not tag(w, 'bridge')]
    first_way = list(osm_root).index(osm_root.find('way'))
    for nid in {r for wid in kept for r in refs[wid]}: osm_root.insert(first_way, fnodes[nid]); osm_nodes[nid] = fnodes[nid]
    joined = 0
    MAIN = ('trunk', 'primary', 'secondary')
    for wid in kept:
        for end in (refs[wid][0], refs[wid][-1]):
            if count[end] != 1: continue                       # not a loose end
            px, py = xy(fnodes[end]); best = None
            for w in surface:
                nds = w.findall('nd')
                for i in range(len(nds) - 1):
                    (ax, ay), (bx, by) = xy(osm_nodes[nds[i].get('ref')]), xy(osm_nodes[nds[i + 1].get('ref')])
                    L2 = (bx - ax) ** 2 + (by - ay) ** 2
                    t = max(0.0, min(1.0, ((px - ax) * (bx - ax) + (py - ay) * (by - ay)) / L2)) if L2 else 0.0
                    qx, qy = ax + t * (bx - ax), ay + t * (by - ay); d = math.dist((px, py), (qx, qy))
                    # prefer a main road within reach (the bridges span the main roads) over a nearer side lane
                    rank = (0 if tag(w, 'highway') in MAIN and d <= FB.get('connect_within_m', 30) else 1, d)
                    if best is None or rank < best[0]: best = (rank, w, nds[i + 1], qx, qy)
            if best is None or best[0][1] > FB.get('connect_within_m', 30): continue
            _, w, before, qx, qy = best
            jid = f"-9{end}"
            node = ET.Element('node', id=jid, lat=f"{qy / KY:.7f}", lon=f"{qx / KX:.7f}", version='1')
            osm_root.insert(first_way, node); osm_nodes[jid] = node
            w.insert(list(w).index(before), ET.Element('nd', ref=jid))
            link = ET.SubElement(osm_root, 'way', id=f"-8{end}", version='1')
            ET.SubElement(link, 'nd', ref=end); ET.SubElement(link, 'nd', ref=jid); ET.SubElement(link, 'tag', k='highway', v='footway')
            joined += 1
    for wid in kept: osm_root.append(fways[wid])
    patched.append(f"foot over bridges: {len(keep)} added ({len(kept)} ways with stairs), {joined} stair feet joined to a carriageway")
osm.write(P('net', 'plain', 'loop_patched.osm.xml'))

# stairs are slow: write their walking speed into a type file (config network.foot_over_bridges.stairs_speed_mps)
with open(P('net', 'plain', 'stairs.typ.xml'), 'w') as f:
    f.write(f'<types><type id="highway.steps" priority="1" numLanes="1" speed="{FB.get("stairs_speed_mps", 1.0)}" allow="pedestrian" oneway="false" width="2"/></types>')

typemaps = ','.join([os.path.join(SUMO_HOME, 'data/typemap/osmNetconvert.typ.xml'),
                     os.path.join(SUMO_HOME, 'data/typemap/osmNetconvertPedestrians.typ.xml'),
                     P('net', 'urban_speeds.typ.xml'), P('net', 'plain', 'stairs.typ.xml')])
tls_opts = ['--tls.cycle.time', str(C['junction_cycle_s']), '--tls.yellow.time', str(C['junction_yellow_s']),
            '--tls.crossing-min.time', str(C['junction_min_ped_green_s']),
            '--tls.default-type', C.get('junction_type', 'static'),          # 'actuated': green follows the queues
            '--tls.min-dur', str(C.get('junction_min_green_s', 5)), '--tls.max-dur', str(C.get('junction_max_green_s', 50))]
# Hosur Road is tagged 60 km/h; netconvert's default guesses no sidewalks/crossings above 50 km/h
ped_opts = ['--sidewalks.guess.max-speed', '20', '--crossings.guess.speed-threshold', '20']
run([BIN('netconvert'), '-c', P('net', 'build.netccfg'), '--osm-files', P('net', 'plain', 'loop_patched.osm.xml'),
     '--type-files', typemaps] + ped_opts + [
     '--output-file', P('net', 'pass1.net.xml')] + tls_opts, log=P('out', 'checks', 'netconvert_pass1.log'))
# junction nodes for A, B and C: unsignalised main-road nodes within the junction's radius joining 3+ road edges
# (nodes pass 1 already signalised are left alone; re-setting them crashes netconvert)
RADIUS = {'A': 40, 'B': 40, 'C': 48}
# Very short approach edges at the main junctions are merged into the junction first. OSM leaves a node a few metres
# before A and C; netconvert turns that into an approach edge 0.2 m long, and a queue-following signal has its sensor
# on that edge, sees nothing and cuts every green to the minimum.
p0 = read_net(P('net', 'pass1.net.xml'))
joins = ET.Element('nodes')
for jid, ll in JUNCTIONS.items():
    x, y = p0.convertLonLat2XY(*ll)
    for n in p0.getNodes():
        if math.dist(n.getCoord(), (x, y)) > RADIUS[jid] or len([e for e in n.getIncoming() + n.getOutgoing() if e.allows('passenger')]) < 3: continue
        for e in n.getIncoming():
            if e.allows('passenger') and e.getLength() < 12 and e.getPriority() >= 11 and e.getFromNode() is not n:
                (ax, ay), (bx, by) = n.getCoord()[:2], e.getFromNode().getCoord()[:2]      # without x/y netconvert leaves the merged node unplaced
                ET.SubElement(joins, 'join', nodes=f"{n.getID()} {e.getFromNode().getID()}", x=f"{ax:.2f}", y=f"{ay:.2f}")
                patched.append(f"junction {jid}: merged the {e.getLength():.1f} m approach edge {e.getID()} into the junction")
if len(joins):
    ET.ElementTree(joins).write(P('net', 'plain', 'short_approach_joins.nod.xml'))
    os.replace(P('net', 'pass1.net.xml'), P('net', 'pass1_unjoined.net.xml'))
    run([BIN('netconvert'), '--sumo-net-file', P('net', 'pass1_unjoined.net.xml'), '--node-files', P('net', 'plain', 'short_approach_joins.nod.xml'),
         '--lefthand', 'true', '--no-warnings', 'true', '--crossings.guess', 'true', '--output-file', P('net', 'pass1.net.xml')] + tls_opts + ped_opts,
        log=P('out', 'checks', 'netconvert_pass1_joins.log'))
p1 = read_net(P('net', 'pass1.net.xml'))
SIGNALISED = C.get('signalised_junctions', list(JUNCTIONS))       # junctions left out get no signal, even if OSM maps one
tls_nodes, unset = [], []
for jid, ll in JUNCTIONS.items():
    x, y = p1.convertLonLat2XY(*ll)
    for n in p1.getNodes():
        road = [e for e in n.getIncoming() + n.getOutgoing() if e.allows('passenger')]
        main = any(e.getPriority() >= 11 for e in road)          # touches a primary/trunk road
        near = math.dist(n.getCoord(), (x, y)) <= RADIUS[jid]
        if jid not in SIGNALISED:
            if near and n.getType().startswith('traffic_light'): unset.append(n.getID())
        elif len(road) >= 3 and main and n.getType() != 'traffic_light' and near: tls_nodes.append(n.getID())
patched.append(f"signals at junctions {', '.join(SIGNALISED)}" + (f"; removed at {len(unset)} node(s) of the others" if unset else ''))
run([BIN('netconvert'), '-c', P('net', 'tls.netccfg'), '--sumo-net-file', P('net', 'pass1.net.xml'),
     '--output-file', P('net', 'base.net.xml')] + (['--tls.set', ','.join(tls_nodes)] if tls_nodes else [])
    + (['--tls.unset', ','.join(unset)] if unset else []) + tls_opts,
    log=P('out', 'checks', 'netconvert_pass2.log'))

# ---- checks --------------------------------------------------------------------------------
net = read_net(P('net', 'base.net.xml'))
lines = [f"OSM correction: {x}" for x in patched]
lines.append(f"edges {len(net.getEdges())}, nodes {len(net.getNodes())}, signals {len(net.getTrafficLights())}")
jxy = {k: net.convertLonLat2XY(*v) for k, v in JUNCTIONS.items()}
for tls in net.getTrafficLights():
    nodes = {c[0].getEdge().getToNode() for c in tls.getConnections()}
    x = sum(n.getCoord()[0] for n in nodes) / len(nodes); y = sum(n.getCoord()[1] for n in nodes) / len(nodes)
    near = min(jxy, key=lambda k: math.dist(jxy[k], (x, y))); d = math.dist(jxy[near], (x, y))
    tag = near if d < 60 else '(outside the loop)'
    for prog in tls.getPrograms().values():
        phases = prog.getPhases()
        cycle = sum(ph.duration for ph in phases)
        # each incoming road edge should get a green at some point
        inc = sorted({c[0].getEdge().getID() for c in tls.getConnections() if c[0].getEdge().allows('passenger')})
        served = set()
        for ph in phases:
            for i, c in enumerate(tls.getConnections()):
                if i < len(ph.state) and ph.state[i] in 'Gg': served.add(c[0].getEdge().getID())
        lines.append(f"signal {tag:18} id={tls.getID()[:40]} cycle={cycle:.0f}s phases={len(phases)} "
                     f"incoming road edges={len(inc)} served={len(set(inc) & served)}")
# sidewalks along each loop carriageway
for (side, fr, to), coords in carriageways().items():
    pts = [net.convertLonLat2XY(*c) for c in coords[::3]]
    have = 0
    for x, y in pts:
        lanes = net.getNeighboringLanes(x, y, 25)
        if any(l.allows('pedestrian') and not l.allows('passenger') for l, _ in lanes): have += 1
    lines.append(f"sidewalk coverage {side} {fr}->{to}: {have}/{len(pts)} sample points have a sidewalk within 25 m")
open(P('out', 'checks', 'network_checks.txt'), 'w').write('\n'.join(lines))
print('\n'.join(lines))
