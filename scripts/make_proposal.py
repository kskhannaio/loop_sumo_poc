"""Step 2b - turn proposals drawn on the website's Draw tab into scenario networks.

For each entry in config "proposals" (a Draw-tab GeoJSON file plus how to read it), builds on today's network
(net/base.net.xml, no metro, tunnel or flyover):

  Zebra crossing / Signalised crossing   a signalised crossing. Mid-block: both carriageways split and joined, with the
                                         same fixed plan as the trial crossings. At a junction: checked against the
                                         junction's own crossings and added if missing.
  new road                               a one-way link between the two nearest roads, in the direction traffic can flow
  New footpath                           a footway between the footpaths of the two nearest roads
  Area of concern, by label              per config "zones": closed_to_traffic | widen_footpath | bus_stop
                                         (bus_stop: moves the nearest existing stop in the same direction into the shape;
                                         a large shape becomes an off-road bay, where a stopped bus leaves the lane)

Writes net/<scenario>.net.xml, net/<scenario>_tls.add.xml, net/<scenario>.proposal.json (bus stop changes, read by
make_demand.py) and out/checks/<scenario>.txt, which says how every drawn feature was applied or why it was not.
"""
import json, math, os, re, shutil, xml.etree.ElementTree as ET
from common import P, cfg, read_net, centrelines, carriageways, JUNCTIONS, SIDE_NAME, LL2M, M2LL, sumolib
import netpatch
from shapely.geometry import LineString, Point, Polygon

C = cfg()
PROPS = {k: v for k, v in C.get('proposals', {}).items() if not k.startswith('_')}
os.makedirs(P('net', 'plain'), exist_ok=True); os.makedirs(P('out', 'checks'), exist_ok=True)
base = read_net(P('net', 'base.net.xml'))
CL, CW = centrelines(), carriageways()
XY = lambda c: base.convertLonLat2XY(*c[:2])
zone_key = lambda s: re.sub(r'\s+', '', s or '').lower()
JN_XY = {k: base.convertLonLat2XY(*v) for k, v in JUNCTIONS.items()}
# nodes of the signals at the loop junctions (a junction can be several nodes joined under one signal)
JN_NODES = {}
for t in base.getTrafficLights():
    for c in t.getConnections():
        n = c[0].getEdge().getToNode()
        j = min(JN_XY, key=lambda k: math.dist(JN_XY[k], n.getCoord()))
        if math.dist(JN_XY[j], n.getCoord()) < 80: JN_NODES[n.getID()] = j


def direction(e, pos):
    """unit direction of edge e at offset pos (metres along it)."""
    shp = e.getShape(); L = e.getLength() or 1
    off = pos * sumolib.geomhelper.polyLength(shp) / L
    a = sumolib.geomhelper.positionAtShapeOffset(shp, max(0, off - 2)); b = sumolib.geomhelper.positionAtShapeOffset(shp, off + 2)
    d = math.dist(a, b) or 1
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def nearest_edges(xy, vclass='passenger', r=25):
    out = []
    for lane, d in base.getNeighboringLanes(xy[0], xy[1], r):
        e = lane.getEdge()
        if e.allows(vclass) and e.getFunction() != 'internal' and all(e is not x[1] for x in out):
            pos = sumolib.geomhelper.polygonOffsetWithMinimumDistanceToPoint(xy, e.getShape()) * e.getLength() / max(1e-6, sumolib.geomhelper.polyLength(e.getShape()))
            out.append((Point(xy).distance(LineString(e.getShape())), e, pos))     # distance to the road's centre, not its nearest lane
    return sorted(out, key=lambda x: x[0])


def variant(scn, spec):
    """A scenario that reuses another one's network (or today's): copies it, then changes how its crossings are run."""
    src = spec.get('network_from')
    if src:
        for suffix in ('.net.xml', '_tls.add.xml', '.proposal.json'):
            if os.path.exists(P('net', f'{src}{suffix}')): shutil.copy(P('net', f'{src}{suffix}'), P('net', f'{scn}{suffix}'))
        report = [f"{scn}: {spec.get('label', '')} - network of {src}"]
    else:
        shutil.copy(P('net', 'base.net.xml'), P('net', f'{scn}.net.xml'))
        for suffix in ('_tls.add.xml', '.proposal.json'):
            if os.path.exists(P('net', f'{scn}{suffix}')): os.remove(P('net', f'{scn}{suffix}'))
        report = [f"{scn}: {spec.get('label', '')} - today's network"]
    cc = spec.get('crossing_control')
    if cc and cc.get('type') == 'actuated':
        root = ET.parse(P('net', f'{scn}_tls.add.xml')).getroot()
        for t in root.findall('tlLogic'):
            t.set('type', 'actuated'); t.set('programID', scn)
            first = t.find('phase')                                   # the vehicle green
            first.set('minDur', str(cc['vehicle_min_green_s'])); first.set('maxDur', str(cc['vehicle_max_green_s']))
        ET.ElementTree(root).write(P('net', f'{scn}_tls.add.xml'))
        report.append(f"new crossings: vehicle-actuated, traffic green {cc['vehicle_min_green_s']}-{cc['vehicle_max_green_s']} s, then people")
    for od, ch in spec.get('demand_change', {}).items():
        if not od.startswith('_'): report.append(f"traffic change (what-if): {od} routed via {ch['via_base_edge']}")
    open(P('out', 'checks', f'{scn}.txt'), 'w').write('\n'.join(report) + '\n')
    print('\n'.join(report))


def build(scn, spec):
    if spec.get('network_from') or not spec.get('file'): return variant(scn, spec)
    feats = json.load(open(P(spec['file'])))['features']
    report = [f"{scn}: {spec.get('label', '')} - {spec['file']}, {len(feats)} drawn features"]
    zones = {zone_key(k): v for k, v in spec.get('zones', {}).items()}
    sites, splits_extra, new_roads, new_paths, bus_moves = [], [], [], [], []
    closed, widened = [], []
    used = {}                                                         # edge id -> [(pos, node id)] extra split points

    def split_point(e, pos, tag):
        """node id of a split of edge e at pos (reusing one within 6 m)."""
        # stay 15 m clear of a loop junction's signal: splitting closer leaves pieces too short for netconvert to keep
        # the junction's own pedestrian crossings (it dropped four at C)
        lo = 15.0 if e.getFromNode().getID() in JN_NODES else 6.0
        hi = e.getLength() - (15.0 if e.getToNode().getID() in JN_NODES else 6.0)
        pos = max(lo, min(hi, pos))
        for p, nid in used.get(e.getID(), []):
            if abs(p - pos) < 6: return nid, p
        nid = f"{tag}_{len(splits_extra)}"
        used.setdefault(e.getID(), []).append((pos, nid)); splits_extra.append((e.getID(), round(pos, 1), nid))
        return nid, pos

    for i, f in enumerate(feats):
        pr, g = f['properties'], f['geometry']; kind = pr.get('change_type', '')
        what = f"#{i} {kind}" + (f" '{pr['label']}'" if pr.get('label') else '')
        if kind in ('Zebra crossing', 'Signalised crossing'):
            mode = spec.get('zebra_crossing', 'signalised')
            if mode not in ('signalised', 'junction_only'):
                report.append(f"{what}: SKIPPED - only signalised crossings are modelled so far"); continue
            xy = XY(g['coordinates'])
            ne = nearest_edges(xy)
            if not ne: report.append(f"{what}: SKIPPED - no road within 25 m"); continue
            d0, e0, pos0 = ne[0]
            # at a junction: the nearest road starts or ends at a loop junction's signal, within 50 m of the point
            arm = [(n, JN_NODES[n.getID()]) for n, gap in ((e0.getFromNode(), pos0), (e0.getToNode(), e0.getLength() - pos0))
                   if n.getID() in JN_NODES and gap < 50]
            if arm:
                node, near_j = arm[0]
                have = [c for c, _ in netpatch.crossings_of(P('net', 'base.net.xml')).get(node.getID(), []) if e0.getID() in c]
                report.append(f"{what}: on the {e0.getName() or e0.getID()} arm of junction {near_j}; " +
                              (f"the model already has a signalised crossing there ({' '.join(have[0])}) - no change" if have else
                               "no crossing there yet - NOT added (add by hand if needed)"))
                continue
            if mode == 'junction_only': report.append(f"{what}: mid-block crossing LEFT OUT in this variant"); continue
            # mid-block: the loop side whose centreline is nearest, both carriageways split opposite each other
            side = min(CL, key=lambda s: netpatch.nearest_on([M2LL(p) for p in CL[s].pts], LL2M(g['coordinates']))[0])
            dist, q, _ = netpatch.nearest_on([M2LL(p) for p in CL[side].pts], LL2M(g['coordinates']))
            if dist > 30: report.append(f"{what}: SKIPPED - {dist:.0f} m from the nearest loop road"); continue
            a, b = side[0], side[1]; ends = []
            for fr, to in ((a, b), (b, a)):
                _, qq, hd = netpatch.nearest_on(CW[(side, fr, to)], q)
                e, pos, _ = netpatch.edge_at(base, M2LL(qq), hd)
                ends.append((e.getID(), round(max(8.0, min(e.getLength() - 8.0, pos)), 1), fr, to))
            ch = min(range(len(CL[side].pts) - 1), key=lambda k: Point(q).distance(LineString(CL[side].pts[k:k + 2])))
            d_along = CL[side].ch[ch] + math.dist(CL[side].pts[ch], q)
            sites.append(dict(side=side, dist_m=round(d_along), ends=ends, what=what))
            report.append(f"{what}: signalised mid-block crossing on {SIDE_NAME[side]}, {d_along:.0f} m from {a} "
                          f"(splits {ends[0][0]}@{ends[0][1]} and {ends[1][0]}@{ends[1][1]})")
        elif kind.lower() == 'new road':
            pts = [XY(c) for c in g['coordinates']]
            ends = [nearest_edges(pts[0], r=20), nearest_edges(pts[-1], r=20)]
            if not ends[0] or not ends[1]: report.append(f"{what}: SKIPPED - an end is not within 20 m of a road"); continue
            # a sketch: each end joins the nearest road; the direction of travel is the one in which the new road leaves
            # one road going forward and joins the other going forward
            def score(e_from, p_from, d_from_m, e_to, p_to, d_to_m, path):
                v0 = (path[1][0] - path[0][0], path[1][1] - path[0][1]); v1 = (path[-1][0] - path[-2][0], path[-1][1] - path[-2][1])
                n0, n1 = math.hypot(*v0) or 1, math.hypot(*v1) or 1
                d_from, d_to = direction(e_from, p_from), direction(e_to, p_to)
                return (v0[0] * d_from[0] + v0[1] * d_from[1]) / n0 + (v1[0] * d_to[0] + v1[1] * d_to[1]) / n1 - (d_from_m + d_to_m) / 40
            best = None
            for path, A, Bn in ((pts, ends[0], ends[1]), (pts[::-1], ends[1], ends[0])):
                for da, ea, pa in A[:1]:
                    for db, eb, pb in Bn[:1]:
                        if ea is eb: continue
                        sc = score(ea, pa, da, eb, pb, db, path)
                        if best is None or sc > best[0]: best = (sc, ea, pa, eb, pb, path)
            if best is None: report.append(f"{what}: SKIPPED - both ends are on the same road"); continue
            _, ea, pa, eb, pb, pts = best
            n_from, pf = split_point(ea, pa, 'pnew'); n_to, pt = split_point(eb, pb, 'pnew')
            same = [k for k, r in enumerate(new_roads) if r[0] == n_from and r[1] == n_to]
            if same:
                k = same[0]; new_roads[k] = new_roads[k][:5] + (new_roads[k][5] + spec['new_road']['lanes'],)
                report.append(f"{what}: joins the same two points as an earlier new road - added as an extra lane to it"); continue
            new_roads.append((n_from, n_to, pts, ea.getID(), eb.getID(), spec['new_road']['lanes']))
            report.append(f"{what}: one-way link from {ea.getName() or ea.getID()} ({ea.getID()}@{pf:.0f}) to "
                          f"{eb.getName() or eb.getID()} ({eb.getID()}@{pt:.0f}), {LineString(pts).length:.0f} m, "
                          f"{spec['new_road']['lanes']} lane(s) at {spec['new_road']['speed_kmh']} km/h")
        elif kind == 'New footpath':
            pts = [XY(c) for c in g['coordinates']]
            ends = [nearest_edges(pts[0], 'pedestrian', 20), nearest_edges(pts[-1], 'pedestrian', 20)]
            ends = [[x for x in e if x[1].allows('passenger')] or e for e in ends]   # join where a road's footpath is
            if not ends[0] or not ends[1]: report.append(f"{what}: SKIPPED - an end is not within 20 m of a footpath"); continue
            (_, ea, pa), (_, eb, pb) = ends[0][0], ends[1][0]
            n_from, pf = split_point(ea, pa, 'pfoot'); n_to, pt = split_point(eb, pb, 'pfoot')
            new_paths.append((n_from, n_to, pts))
            report.append(f"{what}: footway {LineString(pts).length:.0f} m from the footpath of {ea.getName() or ea.getID()} to "
                          f"that of {eb.getName() or eb.getID()}, {spec['new_footpath_width_m']} m wide")
        elif g['type'] == 'Polygon':
            act = zones.get(zone_key(pr.get('label')))
            poly = Polygon([XY(c) for c in g['coordinates'][0]]).buffer(0)
            if not act: report.append(f"{what}: no action for this label - drawn for information only"); continue
            if act == 'bus_stop':
                near = {e.getID(): round(LineString(e.getShape()).distance(poly), 1) for e in base.getEdges()
                        if e.allows('bus') and e.getFunction() != 'internal' and LineString(e.getShape()).distance(poly) <= 40}
                if not near: report.append(f"{what}: bus stop SKIPPED - no road within 40 m"); continue
                lon, lat = base.convertXY2LonLat(poly.centroid.x, poly.centroid.y)
                bay = poly.area >= spec.get('bus_bay_min_area_m2', 200)
                bus_moves.append({'feature': i, 'label': pr.get('label'), 'lonlat': [lon, lat], 'edges_near_m': near, 'bay': bay,
                                  'area_m2': round(poly.area),
                                  'shape': [list(base.convertXY2LonLat(x, y)) for x, y in poly.exterior.coords]})
                report.append(f"{what}: bus stop, {poly.area:.0f} m2 - {'off-road bay: a stopped bus leaves the running lane' if bay else 'kerbside stop'}; "
                              "takes over the nearest existing stop (see the demand check)")
                continue
            hits = []
            for e in base.getEdges():
                if e.getFunction() == 'internal': continue
                inside = LineString(e.getShape()).intersection(poly).length
                if inside > 0.5: hits.append((e, inside))
            if act == 'closed_to_traffic':
                roads = [(e, L) for e, L in hits if e.allows('passenger')]
                shut = [(e, L) for e, L in roads if L >= 15 or L >= 0.5 * e.getLength()]
                closed.extend(e.getID() for e, _ in shut)
                report.append(f"{what}: closed to traffic - " + (', '.join(f"{e.getID()} ({L:.0f} m inside) now footway" for e, L in shut) or
                              'no road runs through it, so nothing changes in the model') +
                              ''.join(f"; {e.getID()} only clipped ({L:.0f} m), left open" for e, L in roads if (e, L) not in shut))
            elif act == 'widen_footpath':
                walks = [(e, L) for e, L in hits if e.allows('pedestrian')]
                widened.extend(e.getID() for e, _ in walks)
                report.append(f"{what}: footpaths widened to {spec['widen_footpath_to_m']} m on " +
                              (', '.join(f"{e.getID()} ({L:.0f} m)" for e, L in walks) or 'nothing - no footpath inside the shape'))
            else: report.append(f"{what}: unknown zone action '{act}' - ignored")
        else:
            report.append(f"{what}: {g['type']} of type '{kind}' has no model meaning yet - drawn for information only")

    # ---- network ---------------------------------------------------------------------------------------
    NR, W = spec['new_road'], spec
    def after_split(split_net):
        edges = ET.Element('edges'); con = ET.Element('connections')
        for k, (a, b, pts, ea, eb, lanes) in enumerate(new_roads):
            # connect explicitly: every vehicle lane of the road it leaves -> the new road -> every vehicle lane of the road it joins
            into = [e for e in split_net.getNode(a).getIncoming() if e.getID().split('.')[0] == ea]
            onto = [e for e in split_net.getNode(b).getOutgoing() if e.getID().split('.')[0] == eb]
            for e in into:
                for l in e.getLanes():
                    if l.allows('passenger'):
                        for tl in range(lanes): ET.SubElement(con, 'connection', attrib={'from': e.getID(), 'to': f"proposal_road{k}", 'fromLane': str(l.getIndex()), 'toLane': str(tl)})
            for e in onto:
                for l in e.getLanes():
                    if l.allows('passenger'):
                        for tl in range(lanes): ET.SubElement(con, 'connection', attrib={'from': f"proposal_road{k}", 'to': e.getID(), 'fromLane': str(tl), 'toLane': str(l.getIndex())})
            ET.SubElement(edges, 'edge', id=f"proposal_road{k}", attrib={'from': a, 'to': b, 'numLanes': str(lanes),
                          'speed': f"{NR['speed_kmh'] / 3.6:.2f}", 'priority': '7', 'disallow': 'pedestrian',
                          'shape': ' '.join(f"{x:.2f},{y:.2f}" for x, y in pts)})
        for k, (a, b, pts) in enumerate(new_paths):
            ET.SubElement(edges, 'edge', id=f"proposal_foot{k}", attrib={'from': a, 'to': b, 'numLanes': '1', 'speed': '1.4',
                          'allow': 'pedestrian', 'width': str(W['new_footpath_width_m']), 'priority': '1',
                          'shape': ' '.join(f"{x:.2f},{y:.2f}" for x, y in pts)})
        # zone edits apply to the pieces the base edges became after splitting
        piece = lambda eid: [e for e in split_net.getEdges() if e.getID() == eid or e.getID().startswith(eid + '.')]
        for eid in closed:
            for e in piece(eid): ET.SubElement(edges, 'edge', id=e.getID(), allow='pedestrian')
        for eid in widened:
            for e in piece(eid):
                el = ET.SubElement(edges, 'edge', id=e.getID())
                for l in e.getLanes():
                    if l.allows('pedestrian') and not l.allows('passenger'):
                        ET.SubElement(el, 'lane', index=str(l.getIndex()), width=str(W['widen_footpath_to_m']))
        return edges, con
    tls_ids, ok = netpatch.build(P('net', 'base.net.xml'), P('net', f'{scn}.net.xml'), sites, P('net', f'{scn}_tls.add.xml'),
                                 scn, 'pxing', scn, splits_extra, after_split)
    net = read_net(P('net', f'{scn}.net.xml'))
    for k, (a, b, _, _, _, _) in enumerate(new_roads):
        e = net.getEdge(f"proposal_road{k}")
        ins, outs = [x.getID() for x in e.getIncoming()], [x.getID() for x in e.getOutgoing()]
        report.append(f"check: new road {k} is fed by {ins or 'NOTHING'} and leads to {outs or 'NOTHING'}")
    for s, tl in zip(sites, tls_ids):
        v = next((x for x in ok if x[0] == tl), (tl, 0, 0))
        report.append(f"check: {s['what']} built as signal {tl} with {v[1]} vehicle and {v[2]} crossing links")
    json.dump({'scenario': scn, 'bus_stops': bus_moves, 'crossings': [{'side': s['side'], 'dist_m': s['dist_m'], 'tls': t}
               for s, t in zip(sites, tls_ids)]}, open(P('net', f'{scn}.proposal.json'), 'w'), indent=1)
    open(P('out', 'checks', f'{scn}.txt'), 'w').write('\n'.join(report) + '\n')
    print('\n'.join(report))


if __name__ == '__main__':
    for scn, spec in sorted(PROPS.items(), key=lambda kv: bool(kv[1].get('network_from'))): build(scn, spec)
