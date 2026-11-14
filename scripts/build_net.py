"""Step 1 - build the base network from OSM and check it.

Pass 1: OSM -> network (left-hand traffic, layer-separated underpass/flyover, urban speeds,
        sidewalks and junction crossings guessed).
Pass 2: signals at junctions B and C (OSM marks them, pass 1 leaves them unsignalised), joined per
        junction, fixed-time plans from config/assumptions.json.
Writes net/base.net.xml and out/checks/network_checks.txt.
"""
import collections, math, os
from common import BIN, P, SUMO_HOME, JUNCTIONS, SIDES, cfg, run, read_net, carriageways, LL2M

C = cfg()['signals']
os.makedirs(P('out', 'checks'), exist_ok=True)
typemaps = ','.join([os.path.join(SUMO_HOME, 'data/typemap/osmNetconvert.typ.xml'),
                     os.path.join(SUMO_HOME, 'data/typemap/osmNetconvertPedestrians.typ.xml'),
                     P('net', 'urban_speeds.typ.xml')])
tls_opts = ['--tls.cycle.time', str(C['junction_cycle_s']), '--tls.yellow.time', str(C['junction_yellow_s']),
            '--tls.crossing-min.time', str(C['junction_min_ped_green_s'])]
# Hosur Road is tagged 60 km/h; netconvert's default guesses no sidewalks/crossings above 50 km/h
ped_opts = ['--sidewalks.guess.max-speed', '20', '--crossings.guess.speed-threshold', '20']
run([BIN('netconvert'), '-c', P('net', 'build.netccfg'), '--type-files', typemaps] + ped_opts + [
     '--output-file', P('net', 'pass1.net.xml')] + tls_opts, log=P('out', 'checks', 'netconvert_pass1.log'))
# junction nodes for A, B and C: unsignalised main-road nodes within the junction's radius joining 3+ road edges
# (nodes pass 1 already signalised are left alone; re-setting them crashes netconvert)
RADIUS = {'A': 40, 'B': 40, 'C': 48}
p1 = read_net(P('net', 'pass1.net.xml'))
tls_nodes = []
for jid, ll in JUNCTIONS.items():
    x, y = p1.convertLonLat2XY(*ll)
    for n in p1.getNodes():
        road = [e for e in n.getIncoming() + n.getOutgoing() if e.allows('passenger')]
        main = any(e.getPriority() >= 11 for e in road)          # touches a primary/trunk road
        if (len(road) >= 3 and main and n.getType() != 'traffic_light'
                and math.dist(n.getCoord(), (x, y)) <= RADIUS[jid]): tls_nodes.append(n.getID())
run([BIN('netconvert'), '-c', P('net', 'tls.netccfg'), '--sumo-net-file', P('net', 'pass1.net.xml'),
     '--tls.set', ','.join(tls_nodes), '--output-file', P('net', 'base.net.xml')] + tls_opts,
    log=P('out', 'checks', 'netconvert_pass2.log'))

# ---- checks --------------------------------------------------------------------------------
net = read_net(P('net', 'base.net.xml'))
lines = []
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
