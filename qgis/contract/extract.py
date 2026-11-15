"""Extract everything drawn on the flyover contract's sheets, on the map.

Needs qgis/contract/out/georef.json from register.py (one fitted transform per PDF page).
Source: "Ejipura to Silk Board Schedule A B C D F H I.pdf" (B-SMILE tender), 17 vector CAD sheets at 1:2000:
topographical survey 1-6 (pages 24-29), general alignment drawing 1-6 (30-35), land acquisition plan 1-5 (36-40).

Writes to qgis/contract/out/ (all in WGS84 unless noted):
  sheets/<set>_<n>.png + .pgw   each sheet's drawing area as an image, world file in UTM 43N (EPSG:32643)
  full_lines.geojsonl           every stroked line (page, set, sheet, colour, width in metres)
  full_polygons.geojsonl        every filled shape (fill and outline colour)
  full_text.geojsonl            every text line (text, rotation for labelling, size in metres)
  contract_structures.geojson   clean named structures, traced by the colour the drawings use for them
  contract_labels.geojson       the drawings' labels for those structures
Run: .venv/bin/python qgis/contract/extract.py [contract.pdf]
"""
import cmath, collections, json, math, os, re, sys
import numpy as np, pymupdf, pyproj
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import unary_union, transform as shp_transform

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PDF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', '..', 'docs', 'Ejipura to Silk Board Schedule A B C D F H I.pdf')
OUT = os.path.join(HERE, 'out'); os.makedirs(os.path.join(OUT, 'sheets'), exist_ok=True)
G = json.load(open(os.path.join(OUT, 'georef.json')))
OFF = G['offset']
SET_CODE = {'Topographical survey': 'topo', 'General alignment drawing': 'gad', 'Land acquisition plan': 'la'}
AREA = pymupdf.Rect(102, 57, 786, 1150)        # inside the border, above the title block (unrotated points)
DPI = 220
to_ll = pyproj.Transformer.from_crs(32643, 4326, always_xy=True).transform
doc = pymupdf.open(PDF)
key = lambda c: tuple(round(v, 2) for v in c) if c else None
hexc = lambda c: '#%02x%02x%02x' % tuple(round(v * 255) for v in c) if c else None

def transform(pno):
    p = G['pages'][str(pno)]['params']
    return math.exp(p[0]) * cmath.exp(1j * p[1]), complex(p[2], p[3])

def utm(a, b, x, y):
    w = a * complex(x, -y) + b
    return (w.real - OFF[0], w.imag - OFF[1])

def ll(a, b, x, y):
    return tuple(round(v, 7) for v in to_ll(*utm(a, b, x, y)))

def bezier(p0, p1, p2, p3, n=8):
    return [((1 - t) ** 3 * p0.x + 3 * (1 - t) ** 2 * t * p1.x + 3 * (1 - t) * t * t * p2.x + t ** 3 * p3.x,
             (1 - t) ** 3 * p0.y + 3 * (1 - t) ** 2 * t * p1.y + 3 * (1 - t) * t * t * p2.y + t ** 3 * p3.y)
            for t in (i / n for i in range(1, n + 1))]

def pieces(d):
    """Split a drawn path into its separate pieces (CAD paths often hold many), curves sampled. -> [(points, closed)]"""
    out, cur, last = [], [], None
    for it in d['items']:
        if it[0] == 're':
            r = it[1]; out.append(([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)], True)); last = None; continue
        if it[0] == 'qu':
            q = it[1]; out.append(([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)], True)); last = None; continue
        a = it[1]
        if last is None or abs(a.x - last.x) + abs(a.y - last.y) > 0.01:
            if len(cur) >= 2: out.append((cur, False))
            cur = [(a.x, a.y)]
        cur += [(it[2].x, it[2].y)] if it[0] == 'l' else bezier(*it[1:5])
        last = it[-1]
    if len(cur) >= 2: out.append((cur, False))
    return [(pts, closed or (len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1]) < 0.01)) for pts, closed in out]

def elongated(d, ratio=2.5):
    """a dash: a filled piece much longer than wide (logos and markers are round)."""
    pts = [(q.x, q.y) for it in d['items'] for q in it[1:] if hasattr(q, 'x')]
    if len(pts) < 3: return False
    P_ = np.array(pts) - np.mean(pts, axis=0); sv = np.linalg.svd(P_, compute_uv=False)
    return sv[0] > ratio * max(sv[1], 1e-6)

def on_frame(pts, tol=12):
    """page-aligned line along the edge of the drawing area: the sheet frame, not drawing content."""
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    vertical, horizontal = max(xs) - min(xs) < 0.5, max(ys) - min(ys) < 0.5
    near = lambda v, edge: abs(v - edge) < tol
    if ((vertical and (near(xs[0], AREA.x0) or near(xs[0], AREA.x1))) or
            (horizontal and (near(ys[0], AREA.y0) or near(ys[0], AREA.y1)))):
        return True
    # view frames inside the area: long outlines made only of page-aligned segments (roads never are)
    segs = list(zip(pts, pts[1:]))
    aligned = all(abs(a[0] - b[0]) < 0.5 or abs(a[1] - b[1]) < 0.5 for a, b in segs)
    return aligned and sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in segs) > 600

# ------------------------------------------------------------------ 1. sheet images
for pno, info in G['pages'].items():
    pno = int(pno); page = doc[pno - 1]; page.set_rotation(0)
    a, b = transform(pno); s = 72 / DPI; ar, ai = a.real, a.imag
    name = f"{SET_CODE[info['set']]}_{info['sheet']}"
    page.get_pixmap(dpi=DPI, clip=AREA).save(os.path.join(OUT, 'sheets', name + '.png'))
    x0, y0 = AREA.x0 + s / 2, AREA.y0 + s / 2
    world = [ar * s, ai * s, ai * s, -ar * s, ar * x0 + ai * y0 + b.real - OFF[0], ai * x0 - ar * y0 + b.imag - OFF[1]]
    open(os.path.join(OUT, 'sheets', name + '.pgw'), 'w').write('\n'.join(f'{v:.6f}' for v in world) + '\n')

# ------------------------------------------------------------------ 2. everything drawn, and 3. named structures
CLASSES = {   # (set, fill colour) -> (layer, what it is). Structures come from the alignment drawings; land from the LA plans.
    ('gad', (0.95, 0.4, 0.13)): ('proposed_deck', 'Proposed elevated corridor deck, Level-1 (loops, rotary, ramps)'),
    ('gad', (0.6, 0.61, 0.22)): ('existing_flyover', 'Existing flyovers, incl. the Silk Board double-decker (olive in the drawings)'),
    ('gad', (0.48, 0.69, 0.87)): ('ejipura_flyover', 'Ejipura flyover approach (under construction)'),
    ('gad', (0.82, 0.61, 0.78)): ('metro', 'Metro line and stations, elevated (lavender in the drawings)'),
    ('gad', (1.0, 0.5, 0.0)): ('orange_structure', None),             # underpass or metro, decided by nearby labels
    ('topo', (1.0, 0.5, 0.0)): ('orange_structure', None),            # the survey sheets draw the Madiwala underpass in orange
    ('gad', (1.0, 0.0, 1.0)): ('metro_tunnel', 'Metro Phase-3A tunnel alignment (underground)'),
    ('gad', (0.7, 1.0, 0.85)): ('bmrcl_land', 'BMRCL (metro) land'),
    ('la', (1.0, 1.0, 0.0)): ('land_acquisition', 'Land to be acquired (land acquisition plan)'),
}
TUNNEL_TEXT = re.compile(r'(16\+\d{3}|tunnel|tube|phase-3a)', re.I)
UNDERPASS_TEXT = re.compile(r'under\s*pass', re.I)
METRO_TEXT = re.compile(r'metro|station|staton', re.I)
KEY_LABEL = re.compile(r'tunnel|tube|metro|station|staton|flyover|ramp|loop|rotary|level|double\s*decker|under\s*pass|underpass|'
                       r'project|bmrcl|bus stand|approach', re.I)

shapes = collections.defaultdict(list)
OCR_FILE = os.path.join(OUT, 'ocr_labels.json')
OCR = json.load(open(OCR_FILE)) if os.path.exists(OCR_FILE) else {}
# the drawings use a small set of label phrases: OCR readings are corrected to the closest one
import difflib
PHRASES = ['Ejipura Flyover', 'Proposed Loop at Level-1', 'Proposed Flyover at Level-1', 'Proposed Rotary at Level-1',
           'Shri Ayyappa Swami Temple', 'End of Level-1 and Start of Level-2', 'End of Level-2 and Start of Level-1',
           'Existing Flyover (Loop) at Level-1', 'Proposed Flyover at Level-2', 'Proposed Loop at Level-2',
           'Elevated Flyover at Level-1 from Marathahalli (ORR)', 'Elevated Flyover at Level-2 from Marathahalli (ORR)',
           'Elevated Flyover at Level-1 from Ragigudda Double Decker Flyover',
           'Proposed Loop at Level-1 from Electronic City Flyover to connect Banashankari Double Decker Flyover',
           'Approach from 100 Feet Road to Electronic City', 'From Banashankari to Electronic City', 'Double Decker Flyover',
           'Double Decker Flyover from Banashankari to Electronic City, approach from 100 Feet Road to Electronic City',
           'Silk Board Flyover at Level-1', 'Approach Ramp', 'Electronic City Flyover at Level-1']
def canonical(t, conf):
    low = t.lower()
    contained = [ph for ph in PHRASES if ph.lower() in low]
    if contained: return max(contained, key=len), 'matched'
    best = max(PHRASES, key=lambda ph: difflib.SequenceMatcher(None, low, ph.lower()).ratio())
    if difflib.SequenceMatcher(None, low, best.lower()).ratio() >= 0.7: return best, 'corrected'
    return (t, 'as read') if conf >= 75 else (None, None)
if not OCR: print('no ocr_labels.json: labels drawn as linework are left out (run ocr.py)')
# the three sets repeat the same base map: keep each drawn entity once, listing every set it appears on
store = {'lines': {}, 'polygons': {}, 'text': {}}
def emit(kind, k, feat, set_name):
    old = store[kind].get(k)
    if old is None:
        feat['properties']['sets'] = [set_name]; store[kind][k] = feat
    elif set_name not in old['properties']['sets']:
        old['properties']['sets'].append(set_name)
rkey = lambda coords: tuple((round(x, 5), round(y, 5)) for x, y in coords)          # ~1 m
labels, seen_labels, counts = [], set(), collections.Counter()
gad_marks = []                                                                     # (text, utm point) on the alignment drawings
approach_dashes = collections.defaultdict(list)                                    # 'START'/'END' -> blue dash centres (utm)
for pno, info in sorted(G['pages'].items(), key=lambda kv: int(kv[0])):
    pno = int(pno); page = doc[pno - 1]; a, b = transform(pno); scale = abs(a)
    setc = SET_CODE[info['set']]
    base = {'page': pno, 'set': info['set'], 'sheet': info['sheet']}
    # text first: it is also used to decide what some coloured shapes are
    texts = []
    for blk in page.get_text('dict')['blocks']:
        for line in blk.get('lines', []):
            t = ' '.join(''.join(s['text'] for s in line['spans']).split())
            if not t: continue
            x0, y0, x1, y1 = line['bbox']
            if not AREA.contains(pymupdf.Point((x0 + x1) / 2, (y0 + y1) / 2)): continue
            dx, dy = line['dir']
            ang = math.degrees(cmath.phase(a * complex(dx, -dy)))            # counter-clockwise from east, on the map
            size = max(s['size'] for s in line['spans']) * scale
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            texts.append((t, cx, cy))
            pt = ll(a, b, cx, cy)
            emit('text', (t, round(pt[0], 5), round(pt[1], 5)), {'type': 'Feature', 'properties': {**base, 'text': t, 'rotation': round(-ang, 1),
                 'size_m': round(size, 2), 'colour': hexc(pymupdf.sRGB_to_pdf(line['spans'][0]['color'])) if 'color' in line['spans'][0] else None},
                 'geometry': {'type': 'Point', 'coordinates': pt}}, info['set'])
            if setc == 'gad': gad_marks.append((t, utm(a, b, cx, cy)))
        # key labels: the whole text block (labels often run over two lines), not clipped at the sheet edge
        parts_ = []
        for ln in blk.get('lines', []):
            t_ = ' '.join(''.join(ch for ch in ''.join(s['text'] for s in ln['spans']) if ch.isprintable()).split())
            if t_ and t_ not in parts_: parts_.append(t_)              # the same label repeated along a line
        bt = ' '.join(parts_).strip()
        x0, y0, x1, y1 = blk['bbox']; inner = pymupdf.Rect(AREA.x0 + 12, AREA.y0 + 12, AREA.x1 - 12, AREA.y1 - 12)
        if (bt and KEY_LABEL.search(bt) and inner.contains(pymupdf.Rect(x0, y0, x1, y1)) and bt.lower() not in seen_labels
                and blk.get('lines')):
            seen_labels.add(bt.lower())
            dx, dy = blk['lines'][0]['dir']; ang = math.degrees(cmath.phase(a * complex(dx, -dy)))
            labels.append({'type': 'Feature', 'properties': {'label': bt, 'rotation': round(-ang, 1), 'source': f"{info['set']} {info['sheet']}"},
                           'geometry': {'type': 'Point', 'coordinates': ll(a, b, (x0 + x1) / 2, (y0 + y1) / 2)}})
    # labels drawn as linework, read by ocr.py
    for o_ in OCR.get(str(pno), []):
        t, how_ = canonical(o_['text'], o_['conf']); cx, cy = o_['x'], o_['y']
        if not t: continue
        if not AREA.contains(pymupdf.Point(cx, cy)): continue
        th = math.radians(o_['angle'])                                         # image angle, y down
        ang = math.degrees(cmath.phase(a * complex(math.cos(th), -math.sin(th))))
        pt = ll(a, b, cx, cy)
        texts.append((t, cx, cy))
        emit('text', (t, round(pt[0], 5), round(pt[1], 5)), {'type': 'Feature', 'properties': {**base, 'text': t, 'rotation': round(-ang, 1),
             'size_m': round(2.5 * scale, 2), 'colour': '#ff00ff', 'ocr': 'yes', 'ocr_conf': o_['conf'], 'ocr_read_as': o_['text'], 'ocr_fix': how_},
             'geometry': {'type': 'Point', 'coordinates': pt}}, info['set'])
        if setc == 'gad': gad_marks.append((t, utm(a, b, cx, cy)))
        if KEY_LABEL.search(t) and t.lower() not in seen_labels:
            seen_labels.add(t.lower())
            labels.append({'type': 'Feature', 'properties': {'label': t, 'rotation': round(-ang, 1),
                           'source': f"{info['set']} {info['sheet']} (linework label read by OCR, {how_})"},
                           'geometry': {'type': 'Point', 'coordinates': pt}})
    near = lambda rx, ry, pat, r: any(pat.search(t) and math.hypot(cx - rx, cy - ry) < r for t, cx, cy in texts)
    for d in page.get_drawings():
        r = d['rect']; rx, ry = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        if not AREA.contains(pymupdf.Point(rx, ry)): continue
        if (r.width > 0.6 * AREA.width or r.height > 0.6 * AREA.height) and all(
                it[0] == 're' or (it[0] == 'l' and (abs(it[1].x - it[2].x) < 0.5 or abs(it[1].y - it[2].y) < 0.5)) for it in d['items']):
            continue                                       # sheet and viewport frames
        fill, stroke = d.get('fill'), d.get('color')
        if fill and (key(fill) == (1.0, 1.0, 1.0) or r.width > 0.6 * AREA.width or r.height > 0.6 * AREA.height):
            continue                                       # white masks and sheet-sized boxes
        props = {**base, 'stroke': hexc(stroke), 'fill': hexc(fill), 'width_m': round((d.get('width') or 0) * scale, 2)}
        polys, hatch = [], []
        for pts, closed in pieces(d):
            if max(abs(p[0] - pts[0][0]) + abs(p[1] - pts[0][1]) for p in pts) < 0.05: continue   # dots of hatch patterns
            if fill and len(pts) >= 3:                     # a fill closes every piece, outlined or not
                g = Polygon([utm(a, b, x, y) for x, y in pts]).buffer(0)
                if not g.is_empty: polys.append(g)
            if fill and len(pts) >= 2:                     # kept as lines too: hatching is drawn as near-flat filled slivers
                hatch.append(LineString([utm(a, b, x, y) for x, y in pts]))
            if stroke and not fill and on_frame(pts): continue
            if stroke and not fill:
                co = [ll(a, b, x, y) for x, y in pts]
                emit('lines', (props['stroke'], rkey(co)), {'type': 'Feature', 'properties': dict(props),
                     'geometry': {'type': 'LineString', 'coordinates': co}}, info['set'])
        if setc == 'gad' and key(fill) == (0.0, 0.0, 1.0) and r.width < 15 and r.height < 15 and elongated(d):
            for t_, tx, ty in texts:
                if t_.upper().replace(' ', '').startswith(('STARTOFAPPROACH', 'ENDOFAPPROACH')) and math.hypot(rx - tx, ry - ty) < 150:
                    approach_dashes[t_.upper().split()[0]].append(utm(a, b, rx, ry))
        cls0 = CLASSES.get((setc, key(fill)))
        if hatch and cls0 and cls0[0] == 'orange_structure':
            # the survey sheets draw the underpass as hatch slivers too: widen and merge, then classify by nearby labels
            lay = 'underpass' if near(rx, ry, UNDERPASS_TEXT, 220) else 'metro' if near(rx, ry, METRO_TEXT, 260) else None
            if lay: shapes[lay].append(unary_union([h.buffer(1.0, cap_style=2) for h in hatch] + polys))
        if hatch and key(fill) == (1.0, 0.0, 1.0) and setc == 'gad' and near(rx, ry, TUNNEL_TEXT, 170):
            # the tunnel is drawn as hatching (Tube 2) or thin walls (Tube 1): widen the strokes and merge
            shapes['metro_tunnel'].append(unary_union([h.buffer(1.0, cap_style=2) for h in hatch] + polys)); hatch = []
        if not polys: continue
        shape = polys[0]
        for g in polys[1:]: shape = shape.symmetric_difference(g) if d.get('even_odd') else shape.union(g)
        if shape.is_empty: continue
        geo = mapping(shp_transform(lambda x, y, z=None: to_ll(x, y), shape))
        c0 = shape.representative_point()
        emit('polygons', (props['fill'], props['stroke'], round(c0.x), round(c0.y), round(shape.area)),
             {'type': 'Feature', 'properties': dict(props), 'geometry': geo}, info['set'])
        cls = CLASSES.get((setc, key(fill)))
        if not cls: continue
        layer = cls[0]
        if layer == 'metro_tunnel': continue                # handled above (magenta is also used for other hatching)
        if layer == 'orange_structure': continue           # handled above
        shapes[layer].append(shape)
for kind, fname in (('lines', 'full_lines.geojsonl'), ('polygons', 'full_polygons.geojsonl'), ('text', 'full_text.geojsonl')):
    with open(os.path.join(OUT, fname), 'w') as f:
        for feat in store[kind].values():
            pr = feat['properties']; pr['sets'] = ', '.join(pr['sets']); pr['set'] = pr['sets'].split(', ')[0]
            f.write(json.dumps(feat) + '\n')
    counts[kind] = len(store[kind])

DESC = {v[0]: v[1] for v in CLASSES.values() if v[1]}
DESC['underpass'] = 'Underpass (existing)'
CLOSE = {'metro_tunnel': 6.0, 'land_acquisition': 0.5}          # the tunnel is drawn as two thin walls
SIMPLIFY, MIN_AREA, MIN_HOLE = 0.4, 15.0, 40.0
# Level-2: the drawings mark where the second level runs ("START / END OF APPROACH ... SECOND LEVEL"). Along Hosur Rd
# between those marks the deck is two levels stacked; the deck there is labelled Level-2 over Level-1.
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from common import sumolib  # noqa: E402
from shapely.geometry import Point, LineString as LS
from shapely.ops import nearest_points
cnet = sumolib.net.readNet(os.path.join(OUT, 'corridor.net.xml'))
hosur = unary_union([LS([(x - OFF[0], y - OFF[1]) for x, y in e.getShape()]) for e in cnet.getEdges()
                     if (e.getName() or '').lower().startswith('hosur')])
# the drawings mark the second level with thick blue dashed lines across the corridor at "START OF APPROACH"
# and "END OF APPROACH" (SECOND LEVEL). Fit a line through each set of dashes; the Level-2 section is the
# deck between the two lines, within 25 m of Hosur Rd (the Level-1 loops and ramps beside it stay Level-1).
def cut_line(pts, along=None, tol=2.5, max_turn=25):
    """robust line through dash centres; with `along`, only directions within max_turn degrees of it."""
    P_ = np.unique(np.round(np.array(pts)), axis=0); best = None       # one vote per dash (a logo draws many points in one spot)
    for i in range(len(P_)):
        for j in range(i + 1, len(P_)):
            d = P_[j] - P_[i]; L = np.hypot(*d)
            if L < 5: continue
            d = d / L
            if along is not None and abs(np.dot(d, along)) < math.cos(math.radians(max_turn)): continue
            n_ = np.array([-d[1], d[0]]); inl = np.abs((P_ - P_[i]) @ n_) < tol
            if best is None or inl.sum() > best[0]: best = (inl.sum(), inl)
    Q = P_[best[1]]; c = Q.mean(axis=0); _, _, vt = np.linalg.svd(Q - c); d = vt[0]
    return LS([tuple(c - 120 * d), tuple(c + 120 * d)]), d, int(best[0])
level2 = None
if len(approach_dashes['START']) >= 3 and len(approach_dashes['END']) >= 3 and 'proposed_deck' in shapes:
    c2, d2, n2 = cut_line(approach_dashes['END'])
    c1, d1, n1 = cut_line(approach_dashes['START'], along=d2)     # both lines cross the same corridor
    (a1, b1), (a2, b2) = list(c1.coords), list(c2.coords)
    if LS([a1, a2]).crosses(LS([b1, b2])): a2, b2 = b2, a2                    # keep the quadrilateral simple
    between = Polygon([a1, b1, b2, a2]).buffer(0)
    # straight axis along Hosur Rd between where the two cut lines meet it; the Level-1 loops lie away from it
    # axis of the main deck: where each cut line crosses the proposed deck. A cut line may cross several strands
    # (main deck and a loop): at START take the crossing nearest Hosur Rd, at END the one that continues the
    # deck's direction (Hosur Rd's bearing at START).
    deck_all = unary_union(shapes['proposed_deck']).buffer(1.5).buffer(-1.5)
    def crossings(cl):
        g = deck_all.intersection(cl)
        return [q.centroid for q in getattr(g, 'geoms', [g]) if not q.is_empty]
    x1, x2 = crossings(c1), crossings(c2)
    p1 = min(x1, key=lambda q: q.distance(hosur))
    h_near = nearest_points(hosur, p1)[0]
    seg = min((LS(e) for e in (getattr(hosur, 'geoms', [hosur])) if LS(e).distance(h_near) < 1), key=lambda l_: l_.distance(h_near))
    hc = list(seg.coords); hb = np.array(hc[-1]) - np.array(hc[0]); hb = hb / np.hypot(*hb)
    p2 = max(x2, key=lambda q: abs(np.dot((np.array(q.coords[0]) - np.array(p1.coords[0])) / max(q.distance(p1), 1e-6), hb)))
    level2 = between.intersection(LS([p1, p2]).buffer(30, cap_style=2))
    json.dump({'start': approach_dashes['START'], 'end': approach_dashes['END'], 'c1': list(c1.coords), 'c2': list(c2.coords)},
              open(os.path.join(OUT, 'level2_debug.json'), 'w'))
    print(f'Level-2 section: cut lines {c1.centroid.distance(c2.centroid):.0f} m apart '
          f'({n1} and {n2} dashes on the lines)')
else:
    print('Level-2 section: blue dashed cut lines not found', {k: len(v) for k, v in approach_dashes.items()})

feats = []
for layer, parts in shapes.items():
    close = CLOSE.get(layer, 1.5)
    g = unary_union(parts).buffer(close, join_style=1).buffer(-close, join_style=1).simplify(SIMPLIFY, preserve_topology=True)
    for p in getattr(g, 'geoms', [g]):
        if p.geom_type != 'Polygon' or p.area < (200 if layer == 'metro_tunnel' else MIN_AREA): continue
        p = Polygon(p.exterior, [r for r in p.interiors if Polygon(r).area >= MIN_HOLE])
        if layer == 'proposed_deck' and level2 is not None and p.intersects(level2):
            pieces2 = [(p.intersection(level2), 'proposed_deck_level2',
                        'Proposed deck: second level over Level-1 (between the drawings\' START and END OF APPROACH, SECOND LEVEL lines)'),
                       (p.difference(level2), 'proposed_deck', DESC['proposed_deck'])]
            for g2, lay2, what2 in pieces2:
                for q in getattr(g2, 'geoms', [g2]):
                    if q.geom_type == 'Polygon' and q.area >= MIN_AREA:
                        feats.append({'type': 'Feature', 'properties': {'layer': lay2, 'what': what2, 'area_m2': round(q.area),
                                      'source': 'B-SMILE elevated-corridor tender drawings, georeferenced to OpenStreetMap (about 1-2 m)'},
                                      'geometry': mapping(shp_transform(lambda x, y, z=None: to_ll(x, y), q))})
            continue
        feats.append({'type': 'Feature', 'properties': {'layer': layer, 'what': DESC[layer], 'area_m2': round(p.area),
                      'source': 'B-SMILE elevated-corridor tender drawings, georeferenced to OpenStreetMap (about 1-2 m)'},
                      'geometry': mapping(shp_transform(lambda x, y, z=None: to_ll(x, y), p))})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'contract_structures.geojson'), 'w'))
json.dump({'type': 'FeatureCollection', 'features': labels}, open(os.path.join(OUT, 'contract_labels.geojson'), 'w'))

n = collections.Counter(f['properties']['layer'] for f in feats)
area = collections.Counter()
for f in feats: area[f['properties']['layer']] += f['properties']['area_m2']
lines = [f"full drawing data: {counts['lines']} lines, {counts['polygons']} filled shapes, {counts['text']} text items",
         *[f'{k}: {v} shapes, {area[k]:,} m2' for k, v in sorted(n.items())], f'key labels: {len(labels)}']
open(os.path.join(OUT, 'extract_report.txt'), 'w').write('\n'.join(lines))
print('\n'.join(lines))
