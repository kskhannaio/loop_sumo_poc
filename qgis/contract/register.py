"""Georeference every drawing sheet in the flyover contract PDF.

Sheets (PDF pages): topographical survey 1-6 = 24-29, general alignment drawing (GAD) 1-6 = 30-35,
land acquisition plan 1-5 = 36-40. All are vector CAD exports at 1:2000.

All sheets are views of one CAD model, so:
1. Chain: every sheet is linked to GAD sheet 2 (page 31) through labels both show inside the drawing area
   (chainage marks, building names...), with a RANSAC similarity fit on the label positions. This puts
   every sheet in page 31's paper coordinates.
2. Fit: one similarity transform (scale, rotation, shift) from those coordinates to the map, optimised so
   the edges of the grey road areas on all sheets land on road edges of a network built from
   OpenStreetMap (osm/corridor.osm.xml -> qgis/contract/out/corridor.net.xml). It starts from a rough
   guess at page 31 (junctions B and C).
Writes qgis/contract/out/georef.json:  utm43 = exp(s)*e^(i*rot)*(x - i*y) + (tx + i*ty) - offset.
Run: .venv/bin/python qgis/contract/register.py [contract.pdf]
"""
import cmath, collections, json, math, os, random, sys
import numpy as np, pymupdf
from scipy.optimize import minimize
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from common import sumolib  # noqa: E402

PDF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', '..', 'docs', 'Ejipura to Silk Board Schedule A B C D F H I.pdf')
OUT = os.path.join(HERE, 'out')
SHEETS = {**{24 + i: ('Topographical survey', i + 1) for i in range(6)},
          **{30 + i: ('General alignment drawing', i + 1) for i in range(6)},
          **{36 + i: ('Land acquisition plan', i + 1) for i in range(5)}}
GREY = (0.5, 0.5, 0.5)

net = sumolib.net.readNet(os.path.join(OUT, 'corridor.net.xml'))
OFF = net.getLocationOffset()
J = {'A': (77.620965, 12.927461), 'B': (77.618093, 12.924584), 'C': (77.614971, 12.929885)}
JX = {k: complex(*net.convertLonLat2XY(*v)) for k, v in J.items()}
key = lambda c: tuple(round(v, 2) for v in c) if c else None

# road outlines: outer edges of the vehicle lanes, sampled every metre
pts = []
for e in net.getEdges():
    lanes = e.getLanes()
    for l in {lanes[0], lanes[-1]}:
        s, w = l.getShape(), l.getWidth() / 2
        for (x1, y1), (x2, y2) in zip(s, s[1:]):
            L = math.hypot(x2 - x1, y2 - y1)
            if not L: continue
            nx, ny = -(y2 - y1) / L, (x2 - x1) / L
            for t in np.arange(0, L, 1.0):
                for sg in (1, -1): pts.append((x1 + (x2 - x1) * t / L + sg * nx * w, y1 + (y2 - y1) * t / L + sg * ny * w))
tree = cKDTree(np.array(pts))

doc = pymupdf.open(PDF)

def road_edges(page):
    z = []
    for d in page.get_drawings():
        if key(d.get('fill')) != GREY: continue
        for it in d['items']:
            if it[0] == 'l':
                a, b = it[1], it[2]; L = max(math.hypot(b.x - a.x, b.y - a.y), 1e-9)
                z += [complex(a.x + (b.x - a.x) * t / L, -(a.y + (b.y - a.y) * t / L)) for t in np.arange(0, L, 1.0)]
            elif it[0] == 'c': z += [complex(q.x, -q.y) for q in it[1:]]
    return np.array(z)

def unique_words(page):
    """label text -> position (page points, y flipped), for labels that occur once on the page."""
    c, pos = collections.Counter(), {}
    for x0, y0, x1, y1, w, *_ in page.get_text('words'):
        if len(w) < 4 or not any(ch.isalpha() or ch == ':' for ch in w): continue
        c[w] += 1; pos[w] = complex((x0 + x1) / 2, -(y0 + y1) / 2)
    return {w: pos[w] for w, n in c.items() if n == 1}

sim = lambda p, z: np.exp(p[0]) * cmath.exp(1j * p[1]) * z + complex(p[2], p[3])
def to_params(a, b): return [math.log(abs(a)), cmath.phase(a), b.real, b.imag]
def from_params(p): return np.exp(p[0]) * cmath.exp(1j * p[1]), complex(p[2], p[3])

def cost(p, z, cap):
    w = sim(p, z); d, _ = tree.query(np.c_[w.real, w.imag], distance_upper_bound=cap)
    return float(np.mean(np.minimum(d, cap) ** 2))

def refine(p, z):
    for cap in (40, 20, 10, 6):
        p = minimize(cost, p, args=(z, cap), method='Nelder-Mead', options={'xatol': 1e-6, 'fatol': 1e-6, 'maxiter': 4000}).x
    return list(map(float, p))

def ransac(pairs, iters=2000, tol=4.0):
    """similarity mapping page-A points -> page-B points from label pairs, robust to wrong matches."""
    best = []
    rnd = random.Random(1)
    for _ in range(iters):
        (z1, w1), (z2, w2) = rnd.sample(pairs, 2)
        if abs(z2 - z1) < 50: continue
        a = (w2 - w1) / (z2 - z1); b = w1 - a * z1
        if not 0.9 < abs(a) < 1.1: continue                 # same drawing scale on every sheet
        inl = [(z, w) for z, w in pairs if abs(a * z + b - w) < tol]
        if len(inl) > len(best): best = inl
    if len(best) < 3: return None, 0
    Z = np.array([z for z, _ in best]); W = np.array([w for _, w in best])
    A = np.c_[Z, np.ones(len(Z))]; sol = np.linalg.lstsq(A, W, rcond=None)[0]
    return (sol[0], sol[1]), len(best)

AREA = pymupdf.Rect(110, 60, 780, 1145)       # inside the border, above the title block (unrotated points)
def unique_words_in_area(page):
    return {w: z for w, z in unique_words(page).items() if AREA.contains(pymupdf.Point(z.real, -z.imag))}

def ransac_same_scale(pairs, iters=3000, tol=2.5):
    best = []; rnd = random.Random(1)
    for _ in range(iters):
        (z1, w1), (z2, w2) = rnd.sample(pairs, 2)
        if abs(z2 - z1) < 60: continue
        a = (w2 - w1) / (z2 - z1)
        if not 0.98 < abs(a) < 1.02: continue              # every sheet is drawn at the same scale
        b = w1 - a * z1
        inl = [(z, w) for z, w in pairs if abs(a * z + b - w) < tol]
        if len(inl) > len(best): best = inl
    if len(best) < 4: return None, 0, None
    Z = np.array([z for z, _ in best]); W = np.array([w for _, w in best])
    sol = np.linalg.lstsq(np.c_[Z, np.ones(len(Z))], W, rcond=None)[0]
    res = np.abs(sol[0] * Z + sol[1] - W)
    return (sol[0], sol[1]), len(best), float(np.median(res))

REF = 31
words = {p: unique_words_in_area(doc[p - 1]) for p in SHEETS}
chain, how = {REF: (1 + 0j, 0j)}, {REF: 'reference sheet'}     # page -> (a, b): page coords -> page-31 coords
todo = [p for p in SHEETS if p != REF]
while todo:
    best = None
    for p in todo:
        for q in chain:
            shared = [(words[p][w], words[q][w]) for w in set(words[p]) & set(words[q])]
            if len(shared) < 6: continue
            m, n, r = ransac_same_scale(shared)
            if m and n >= 6 and (best is None or n > best[3]): best = (p, q, m, n, r)
    if best is None:      # fallback for sheets with little overlap: same orientation, pure shift agreed by >= 2 labels
        for p in todo:
            for q in chain:
                shared = [(words[p][w], words[q][w]) for w in set(words[p]) & set(words[q])]
                if len(shared) < 2: continue
                shifts = np.array([w - z for z, w in shared]); b = complex(np.median(shifts.real), np.median(shifts.imag))
                inl = [x for x in shifts if abs(x - b) < 3]
                if len(inl) >= 2 and (best is None or len(inl) > best[3]):
                    best = (p, q, (1 + 0j, complex(np.mean(np.real(inl)), np.mean(np.imag(inl)))), len(inl),
                            float(np.median([abs(x - b) for x in inl])))
        if best is None: sys.exit(f'could not link pages {todo} by shared labels')
    p, q, (a, b), n, r = best
    aq, bq = chain[q]
    chain[p] = (aq * a, aq * b + bq)
    how[p] = f'linked to page {q} by {n} shared labels (label fit {r * 0.69:.1f} m)'
    todo.remove(p)

# one transform from page-31 coordinates to the map, fitted on the road edges of every sheet
z_all = np.concatenate([chain[p][0] * road_edges(doc[p - 1]) + chain[p][1] for p in SHEETS])
zb, zc = complex(455, -1030), complex(455, -1030 + abs(JX['C'] - JX['B']) / 0.69)
a0 = (JX['C'] - JX['B']) / (zc - zb)
g = refine(to_params(a0, JX['B'] - a0 * zb), z_all)
ag, bg = from_params(g)
fits = {p: to_params(ag * chain[p][0], ag * chain[p][1] + bg) for p in SHEETS}
report = []
for p in sorted(fits):
    z = road_edges(doc[p - 1]); s, n = SHEETS[p]
    if len(z) > 200:
        w = sim(fits[p], z); d, _ = tree.query(np.c_[w.real, w.imag])
        fit_txt = f'road edges median {np.median(d):.2f} m, {np.mean(d < 3) * 100:.0f}% within 3 m'
    else:
        fit_txt = 'few grey roads on this sheet'
    report.append(f'page {p} {s} {n}: scale {math.exp(fits[p][0]):.4f} m/pt, rotation {math.degrees(fits[p][1]):7.2f} deg, '
                  f'{fit_txt} ({how[p]})')
json.dump({'pages': {str(p): {'set': SHEETS[p][0], 'sheet': SHEETS[p][1], 'params': fits[p], 'how': how[p]} for p in sorted(fits)},
           'offset': OFF, 'formula': 'utm43 = exp(p0)*e^(i*p1)*(x - i*y) + (p2 + i*p3) - offset; x, y in unrotated PDF points'},
          open(os.path.join(OUT, 'georef.json'), 'w'), indent=1)
open(os.path.join(OUT, 'georef_report.txt'), 'w').write('\n'.join(report))
print('\n'.join(report))
