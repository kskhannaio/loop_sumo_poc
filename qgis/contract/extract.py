"""Georeference the flyover contract's drawings and extract planned structures as map layers.

Source: "Ejipura to Silk Board Schedule A B C D F H I.pdf" (B-SMILE tender), General Alignment Drawing
sheets 1 and 2 (PDF pages 30 and 31), which cover the Madiwala loop. The pages are vector CAD exports.

1. Fit: for each sheet, a similarity transform (scale, rotation, shift) is fitted so that the edges of the
   drawing's grey at-grade road areas land on road edges from our SUMO network (OpenStreetMap).
2. Images: each sheet's drawing area is rendered to PNG with a world file in UTM 43N (EPSG:32643).
3. Layers: planned structures are picked out by the fill colour the drawing uses for them, and labels by
   their text, and written as GeoJSON (WGS84).

Run with the project venv (needs pymupdf, scipy, shapely):
    .venv/bin/python qgis/contract/extract.py [path/to/contract.pdf]
Outputs go to qgis/contract/out/.
"""
import json, math, cmath, os, sys
import numpy as np, pymupdf
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, LineString, mapping
from shapely.ops import unary_union, transform as shp_transform
import pyproj

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from common import P, sumolib  # noqa: E402

PDF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', '..', 'docs', 'Ejipura to Silk Board Schedule A B C D F H I.pdf')
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
SHEETS = {30: 'GAD sheet 1 (Sarjapura junction to Madiwala)', 31: 'GAD sheet 2 (St John\'s to Madiwala)'}
DRAWING_AREA = pymupdf.Rect(102, 57, 786, 1150)        # page area inside the border, above the title block (unrotated pt)
DPI = 220
NOMINAL = 0.7056                                        # 1:2000 on paper, metres per PDF point

net = sumolib.net.readNet(P('net', 'base.net.xml'))
OFF = net.getLocationOffset()                           # SUMO xy = UTM 43N + offset
J = {'A': (77.620965, 12.927461), 'B': (77.618093, 12.924584), 'C': (77.614971, 12.929885)}
JX = {k: complex(*net.convertLonLat2XY(*v)) for k, v in J.items()}
to_ll = pyproj.Transformer.from_crs(32643, 4326, always_xy=True).transform
doc = pymupdf.open(PDF)
key = lambda c: tuple(round(v, 2) for v in c) if c else None

# ------------------------------------------------------------------ 1. fit each sheet to the network
outline = []
for e in net.getEdges():
    veh = [l for l in e.getLanes() if l.allows('passenger') or l.allows('bus')]
    for l in (veh[0], veh[-1]) if veh else ():
        s, w = l.getShape(), l.getWidth() / 2
        for (x1, y1), (x2, y2) in zip(s, s[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if not L: continue
            nx, ny = -(y2 - y1) / L, (x2 - x1) / L
            for t in np.arange(0, L, 1.0):
                for sg in (1, -1): outline.append((x1 + (x2 - x1) * t / L + sg * nx * w, y1 + (y2 - y1) * t / L + sg * ny * w))
tree = cKDTree(np.array(outline))

def road_edges(page):
    z = []
    for d in page.get_drawings():
        if key(d.get('fill')) != (0.5, 0.5, 0.5): continue
        for it in d['items']:
            if it[0] == 'l':
                a, b = it[1], it[2]; L = max(math.hypot(b.x - a.x, b.y - a.y), 1e-9)
                z += [complex(a.x + (b.x - a.x) * t / L, -(a.y + (b.y - a.y) * t / L)) for t in np.arange(0, L, 1.0)]
            elif it[0] == 'c': z += [complex(q.x, -q.y) for q in it[1:]]
    return np.array(z)

sim = lambda p, z: np.exp(p[0]) * cmath.exp(1j * p[1]) * z + complex(p[2], p[3])
def cost(p, z, cap):
    w = sim(p, z); d, _ = tree.query(np.c_[w.real, w.imag], distance_upper_bound=cap)
    return float(np.mean(np.minimum(d, cap) ** 2))
def start(z1, w1, z2, w2):
    a = (w2 - w1) / (z2 - z1); b = w1 - a * z1
    return [math.log(abs(a)), cmath.phase(a), b.real, b.imag]

STARTS = {   # rough first guesses read off the sheets: (page point, map point) pairs
    30: (complex(485, -292), JX['A'], complex(315, -850), JX['B']),
    31: (complex(455, -1030), JX['B'], complex(455, -1030 + abs(JX['C'] - JX['B']) / NOMINAL), JX['C']),
}
fits, report = {}, []
for pno in SHEETS:
    z = road_edges(doc[pno - 1]); p = start(*STARTS[pno])
    for cap in (40, 20, 10, 6):
        p = minimize(cost, p, args=(z, cap), method='Nelder-Mead', options={'xatol': 1e-6, 'fatol': 1e-6, 'maxiter': 4000}).x
    w = sim(p, z); d, _ = tree.query(np.c_[w.real, w.imag])
    fits[pno] = list(map(float, p))
    report.append(f'page {pno}: scale {math.exp(p[0]):.4f} m/pt (1:2000 = {NOMINAL}), rotation {math.degrees(p[1]):.2f} deg, '
                  f'median road-edge distance {np.median(d):.2f} m, {np.mean(d < 3) * 100:.0f}% within 3 m')
json.dump({'fits': fits, 'note': 'sumo_xy = exp(s) * e^(i*rot) * (x - i*y) + (tx + i*ty); x, y in unrotated PDF points; '
           'UTM 43N = sumo_xy - offset', 'offset': OFF}, open(os.path.join(OUT, 'georef.json'), 'w'), indent=1)

def page_to_ll(pno):
    p = fits[pno]; a = math.exp(p[0]) * cmath.exp(1j * p[1]); b = complex(p[2], p[3])
    def f(x, y):
        w = a * complex(x, -y) + b
        return to_ll(w.real - OFF[0], w.imag - OFF[1])
    return f

# ------------------------------------------------------------------ 2. sheet images with world files
for pno in SHEETS:
    page = doc[pno - 1]; page.set_rotation(0)
    pix = page.get_pixmap(dpi=DPI, clip=DRAWING_AREA)
    name = f'contract_sheet_{pno - 29}'
    pix.save(os.path.join(OUT, name + '.png'))
    p = fits[pno]; a = math.exp(p[0]) * cmath.exp(1j * p[1]); b = complex(p[2], p[3]); s = 72 / DPI
    ar, ai = a.real, a.imag
    x0, y0 = DRAWING_AREA.x0 + s / 2, DRAWING_AREA.y0 + s / 2               # pixel centres
    # UTM X = ar*x + ai*y + Re(b) - offx ;  UTM Y = ai*x - ar*y + Im(b) - offy ;  x = x0 + col*s, y = y0 + row*s
    world = [ar * s, ai * s, ai * s, -ar * s, ar * x0 + ai * y0 + b.real - OFF[0], ai * x0 - ar * y0 + b.imag - OFF[1]]
    open(os.path.join(OUT, name + '.pgw'), 'w').write('\n'.join(f'{v:.6f}' for v in world) + '\n')

# ------------------------------------------------------------------ 3. planned structures by fill colour
CLASSES = {   # fill colour -> (layer, what it is)
    (0.95, 0.4, 0.13): ('proposed_flyover', 'Proposed elevated corridor deck (Level-1 loop, rotary and ramps)'),
    (0.48, 0.69, 0.87): ('ejipura_flyover', 'Ejipura flyover approach (under construction)'),
    (0.7, 1.0, 0.85): ('bmrcl_land', 'BMRCL (metro) land'),
    (1.0, 0.0, 1.0): ('metro_tunnel', 'Metro Phase-3A tunnel alignment'),
}
TUNNEL_NEAR = ('Tube', 'Tunnel', 'Phase-3A', '16+571', '16+600', '16+745')   # magenta is also used for other things
polys = {c: [] for c in CLASSES}
for pno in SHEETS:
    page, f = doc[pno - 1], page_to_ll(pno)
    anchors = [r for t in TUNNEL_NEAR for r in page.search_for(t)]
    for d in page.get_drawings():
        k = key(d.get('fill'))
        if k not in CLASSES: continue
        if k == (1.0, 0.0, 1.0) and not any(math.dist(((d['rect'].x0 + d['rect'].x1) / 2, (d['rect'].y0 + d['rect'].y1) / 2),
                                                      ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)) < 160 for r in anchors):
            continue
        ring = []
        for it in d['items']:
            if it[0] == 'l': ring += [it[1], it[2]]
            elif it[0] == 'c': ring += [it[1], it[4]]
            elif it[0] == 're': r = it[1]; ring += [r.tl, r.tr, r.br, r.bl]
            elif it[0] == 'qu': q = it[1]; ring += [q.ul, q.ur, q.lr, q.ll]
        if len(ring) >= 3:
            g = Polygon([f(q.x, q.y) for q in ring]).buffer(0)
            if not g.is_empty: polys[k].append(g)
feats = []
for k, (layer, desc) in CLASSES.items():
    if not polys[k]: continue
    u = unary_union(polys[k]).buffer(0.000002).buffer(-0.000002)     # close hairline gaps between drawn pieces
    for g in getattr(u, 'geoms', [u]):
        if g.area < 1e-10: continue
        feats.append({'type': 'Feature', 'properties': {'layer': layer, 'what': desc,
                      'source': 'B-SMILE contract GAD sheets 1-2, georeferenced; positions approximate (~2 m)'},
                      'geometry': mapping(g)})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(OUT, 'contract_structures.geojson'), 'w'))

# ------------------------------------------------------------------ labels from the drawing's own text
LABELS = ['End of Tunnel Tube 1', 'Metro Line (Phase-3A)', 'Proposed Loop at Level-1', 'Proposed Rotary at Level-1',
          'Proposed Flyover at Level-1', 'Exit Ramp 01', 'Entry Ramp 08', 'Flyover Under Construction Approach',
          'KORAMANGALA 2nd BLOCK']        # 'Ejipura Flyover' left out: on the drawing it is a callout far from the flyover
labels, seen = [], set()
for pno in SHEETS:
    page, f = doc[pno - 1], page_to_ll(pno)
    for b in page.get_text('blocks'):
        text = ' '.join(b[4].split())
        for want in LABELS:
            if want.lower().replace(' ', '') in text.lower().replace(' ', '') and want not in seen:
                lon, lat = f((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                labels.append({'type': 'Feature', 'properties': {'label': want, 'sheet': SHEETS[pno]},
                               'geometry': {'type': 'Point', 'coordinates': [lon, lat]}})
                seen.add(want)
json.dump({'type': 'FeatureCollection', 'features': labels}, open(os.path.join(OUT, 'contract_labels.geojson'), 'w'))

import collections
n = collections.Counter(f['properties']['layer'] for f in feats)
open(os.path.join(OUT, 'report.txt'), 'w').write('\n'.join(report + [f'{k}: {v} polygons' for k, v in n.items()] +
                                                       [f'labels found: {sorted(seen)}', f'labels missing: {sorted(set(LABELS) - seen)}']))
print(open(os.path.join(OUT, 'report.txt')).read())
