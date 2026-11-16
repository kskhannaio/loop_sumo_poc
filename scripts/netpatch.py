"""Shared network surgery for scenario networks (trial crossings, drawn proposals).

build(...) takes a base network and
  - splits edges at given positions (mid-block crossing sites, ends of new roads and footpaths),
  - restores the junction crossings netconvert drops when an edge next to a junction is split,
  - joins the two split points of each crossing site into one signalised junction with a crossing,
  - adds any new edges (new roads, new footpaths) and edge changes supplied by the caller,
  - writes a fixed pedestrian-friendly signal plan for each crossing site.
"""
import collections, math, xml.etree.ElementTree as ET
from common import BIN, P, cfg, run, read_net, LL2M, sumolib


def nearest_on(coords, p):
    """(distance, nearest point, segment direction) from metric point p to a lon/lat polyline."""
    best = (1e18, None, None)
    pts = [LL2M(c) for c in coords]
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2)) if L2 else 0
        q = (a[0] + t * dx, a[1] + t * dy)
        if math.dist(p, q) < best[0]: best = (math.dist(p, q), q, (dx, dy))
    return best


def edge_at(net, lonlat, heading_m, vclass='passenger', r=25):
    """Edge under a point whose direction matches heading_m (metric dx, dy); returns (edge, pos along edge, distance)."""
    x, y = net.convertLonLat2XY(*lonlat)
    best = None
    for lane, d in net.getNeighboringLanes(x, y, r):
        e = lane.getEdge()
        if not e.allows(vclass) or d > r: continue
        shp = e.getShape(); off = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint((x, y), shp)
        i = max(1, min(len(shp) - 1, next((k for k in range(1, len(shp)) if sumolib.geomhelper.polyLength(shp[:k + 1]) >= off), len(shp) - 1)))
        ex, ey = shp[i][0] - shp[i - 1][0], shp[i][1] - shp[i - 1][1]
        if heading_m is not None and ex * heading_m[0] + ey * heading_m[1] <= 0: continue
        if best is None or d < best[2]:
            best = (e, off * e.getLength() / max(1e-6, sumolib.geomhelper.polyLength(shp)), d)
    return best


def crossings_of(path):
    """{node: [(crossed edge ids, width)]} for every pedestrian crossing in a network file."""
    r = ET.parse(path).getroot(); out = {}
    for e in r.findall('edge'):
        if e.get('function') == 'crossing':
            node = e.get('id')[1:e.get('id').rindex('_c')]
            out.setdefault(node, []).append((tuple(e.get('crossingEdges').split()), e.find('lane').get('width')))
    return out


def build(base_path, out_path, sites, tls_add_path, program_id, prefix, log_tag, splits_extra=(), after_split=None):
    """sites: [{'ends': [(edge id, pos, ...), (edge id, pos, ...)]}] - one per crossing, one end per carriageway.
    splits_extra: [(edge id, pos, node id)] extra split points (ends of new roads / footpaths).
    after_split(split_net) -> (edges element or None, connections element or None) for pass B.
    Returns (tls ids, [(tls id, vehicle links, crossing links)])."""
    C = cfg(); M = C['signals']
    splits = collections.defaultdict(list)
    for k, s in enumerate(sites):
        s['nodes'] = []
        for j, end in enumerate(s['ends']):
            nid = f"{prefix}{k}_{'ab'[j]}"
            splits[end[0]].append((end[1], nid)); s['nodes'].append(nid)
    for eid, pos, nid in splits_extra: splits[eid].append((pos, nid))
    patch = ET.Element('edges')
    for eid, items in splits.items():
        el = ET.SubElement(patch, 'edge', id=eid)
        for pos, nid in sorted(items):
            ET.SubElement(el, 'split', pos=str(pos), id=nid)
    ET.ElementTree(patch).write(P('net', 'plain', f'{log_tag}_splits.edg.xml'))
    joins = ET.Element('nodes')
    for s in sites: ET.SubElement(joins, 'join', nodes=' '.join(s['nodes']))
    ET.ElementTree(joins).write(P('net', 'plain', f'{log_tag}_joins.nod.xml'))
    tls_ids = ['cluster_' + '_'.join(sorted(s['nodes'])) for s in sites]

    # pass A: split (netconvert remaps connections itself)
    split_path = P('net', 'plain', f'{log_tag}_split.net.xml')
    run([BIN('netconvert'), '-s', base_path, '--edge-files', P('net', 'plain', f'{log_tag}_splits.edg.xml'),
         '--lefthand', 'true', '--walkingareas', 'true', '--output.street-names', 'true', '--no-warnings', 'true',
         '--output-file', split_path], log=P('out', 'checks', f'netconvert_{log_tag}_split.log'))
    # Splitting renames the edge piece next to a junction (E -> E.<pos>), and netconvert then drops every junction
    # crossing that referenced E. Re-declare them with remapped edge ids.
    before, after = crossings_of(base_path), crossings_of(split_path)
    split_net = read_net(split_path)
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
    extra_edges, extra_con = after_split(split_net) if after_split else (None, None)
    if extra_con is not None:
        for c in extra_con: restore.append(c)
    ET.ElementTree(restore).write(P('net', 'plain', f'{log_tag}_restore.con.xml'))
    print(f'restored {n_restored} junction crossings lost by splitting')

    # pass B: joins, new edges, crossings, signals
    cmd = [BIN('netconvert'), '-s', split_path, '--node-files', P('net', 'plain', f'{log_tag}_joins.nod.xml'),
           '--connection-files', P('net', 'plain', f'{log_tag}_restore.con.xml')]
    if extra_edges is not None and len(extra_edges):
        ET.ElementTree(extra_edges).write(P('net', 'plain', f'{log_tag}_new.edg.xml'))
        cmd += ['--edge-files', P('net', 'plain', f'{log_tag}_new.edg.xml')]
    cmd += ['--lefthand', 'true', '--crossings.guess', 'true', '--crossings.guess.speed-threshold', '20', '--walkingareas', 'true',
            '--no-turnarounds', 'true']
    if tls_ids:
        cmd += ['--tls.set', ','.join(tls_ids), '--tls.default-type', 'static', '--tls.cycle.time', str(M['midblock_cycle_s'])]
    cmd += ['--output.street-names', 'true', '--no-warnings', 'true', '--output-file', out_path]
    run(cmd, log=P('out', 'checks', f'netconvert_{log_tag}.log'))

    # fixed pedestrian-friendly plan for each new crossing
    root = ET.parse(out_path).getroot()
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
        prog = ET.SubElement(add, 'tlLogic', id=tl, type='static', programID=program_id, offset='0')
        for dur, s in ((veh_green, st('G', 'r')), (M['midblock_yellow_s'], st('y', 'r')), (2, st('r', 'r')),
                       (M['midblock_ped_green_s'], st('r', 'G')), (2, st('r', 'r'))):
            ET.SubElement(prog, 'phase', duration=str(dur), state=s)
        ok.append((tl, sum(1 for v in lk.values() if v == 'veh'), sum(1 for v in lk.values() if v == 'ped')))
    ET.ElementTree(add).write(tls_add_path)
    missing = [tl for tl in tls_ids if tl not in links]
    if missing: raise SystemExit(f'{log_tag}: crossings not built: {missing}')
    # guard: the new network must keep every base crossing (it only adds new ones)
    n_base = sum(len(v) for v in crossings_of(base_path).values())
    n_out = sum(len(v) for v in crossings_of(out_path).values())
    n_new = sum(len(v) for k, v in crossings_of(out_path).items() if k.startswith('cluster_' + prefix))
    print(f'crossings: base {n_base}, {log_tag} {n_out} ({n_new} at new crossing sites)')
    if n_out - n_new < n_base: raise SystemExit(f'{log_tag} network lost {n_base - (n_out - n_new)} base crossings')
    b_x, o_x = crossings_of(base_path), crossings_of(out_path)
    lost = {n: len(v) - len(o_x.get(n, [])) for n, v in b_x.items() if len(o_x.get(n, [])) < len(v)}
    if lost: raise SystemExit(f'{log_tag}: crossings lost at existing junctions: ' + ', '.join(f'{n[:40]} ({k})' for n, k in lost.items()))
    return tls_ids, ok
