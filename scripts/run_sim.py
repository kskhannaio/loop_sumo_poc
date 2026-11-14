"""Step 4 - run SUMO for each scenario (or the ones given on the command line).

Outputs per scenario in out/<scenario>/: tripinfo.xml (vehicles, buses, people), stats.xml (teleports,
collisions), edgedata.xml (vehicles + people per edge, 08:00-09:00, incl. crossings), queues.xml (E2
detectors on every approach to the A/B/C and trial signals), sumo.log.
"""
import math, os, sys, time, xml.etree.ElementTree as ET
from common import BIN, P, SCENARIOS, JUNCTIONS, cfg, hhmm, run, read_net

C = cfg(); T = C['time']
B, E = hhmm(T['sim_begin']), hhmm(T['sim_end'])
M0, M1 = hhmm(T['metrics_begin']), hhmm(T['metrics_end'])

def signal_ids(net, scn):
    """{label: tls id} for junctions A, B, C and the trial crossings."""
    out = {}
    for tls in net.getTrafficLights():
        nodes = {c[0].getEdge().getToNode() for c in tls.getConnections()}
        x = sum(n.getCoord()[0] for n in nodes) / len(nodes); y = sum(n.getCoord()[1] for n in nodes) / len(nodes)
        if tls.getID().startswith('cluster_xing'):
            out['X' + tls.getID().split('xing')[1].split('_')[0]] = tls.getID(); continue
        for j, ll in JUNCTIONS.items():
            if math.dist(net.convertLonLat2XY(*ll), (x, y)) < 60: out[j] = tls.getID()
    return out

def write_detectors(net, scn, path):
    add = ET.Element('additional')
    ET.SubElement(add, 'edgeData', id='veh', file='edgedata.xml', begin=str(M0), end=str(M1))
    ET.SubElement(add, 'edgeData', id='ped', file='edgedata_people.xml', begin=str(M0), end=str(M1),
                  detectPersons='walk', withInternal='true', excludeEmpty='true')
    sig = signal_ids(net, scn)
    for label, tid in sig.items():
        tls = net.getTLS(tid)
        lanes = {c[0] for c in tls.getConnections() if c[0].allows('passenger')}
        for lane in lanes:
            L = lane.getLength() - 0.1                      # detectors must end strictly inside the lane
            if L < 2: continue
            ET.SubElement(add, 'laneAreaDetector', id=f"q_{label}_{lane.getID()}", lane=lane.getID(),
                          pos=f"{max(0.0, L - 150):.2f}", endPos=f"{L:.2f}", period='1800', file='queues.xml')
    ET.ElementTree(add).write(path)
    return sig

def run_scenario(scn):
    d = P('out', scn); os.makedirs(d, exist_ok=True)
    net = read_net(P('net', f'{scn}.net.xml'))
    sig = write_detectors(net, scn, os.path.join(d, 'detectors.add.xml'))
    adds = [P('demand', scn, 'busstops.add.xml'), os.path.join(d, 'detectors.add.xml')]
    if scn != 'baseline': adds.append(P('net', 'trial_tls.add.xml'))
    cmd = [BIN('sumo'), '-n', P('net', f'{scn}.net.xml'),
           '-r', ','.join(P('demand', scn, f) for f in ('vehicles.rou.xml', 'buses.rou.xml', 'persons.rou.xml')),
           '-a', ','.join(adds),
           '--begin', str(B), '--end', str(E), '--step-length', str(T['step_length_s']),
           '--lateral-resolution', str(T['lateral_resolution_m']), '--seed', str(T['seed']),
           '--pedestrian.model', 'striping', '--time-to-teleport', '300', '--ignore-route-errors', 'true',
           '--collision.action', 'warn', '--collision.mingap-factor', '0',
           '--tripinfo-output', os.path.join(d, 'tripinfo.xml'), '--tripinfo-output.write-unfinished', 'true',
           '--statistic-output', os.path.join(d, 'stats.xml'), '--duration-log.statistics', 'true',
           '--no-step-log', 'true', '--no-warnings', 'false', '--log', os.path.join(d, 'sumo.log')]
    t = time.time()
    run(cmd, log=os.path.join(d, 'sumo.stdout'))
    with open(os.path.join(d, 'signals.txt'), 'w') as f:
        for k, v in sig.items(): f.write(f"{k}\t{v}\n")
    st = ET.parse(os.path.join(d, 'stats.xml')).getroot()
    tp, col = st.find('teleports'), st.find('safety/collisions') if st.find('safety') is not None else None
    vs = st.find('vehicles'); ps = st.find('persons')
    print(f"{scn}: {time.time() - t:.0f}s  vehicles loaded {vs.get('loaded')} inserted {vs.get('inserted')} running-at-end {vs.get('running')} "
          f"| teleports {tp.get('total')} (jam {tp.get('jam')}, yield {tp.get('yield')}, wrongLane {tp.get('wrongLane')}) "
          f"| collisions {st.find('safety').get('collisions') if st.find('safety') is not None else '?'} "
          f"| people loaded {ps.get('loaded') if ps is not None else '?'}")

if __name__ == '__main__':
    for scn in (sys.argv[1:] or SCENARIOS): run_scenario(scn)
