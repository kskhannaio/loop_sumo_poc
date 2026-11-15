"""Read the labels the contract drawings draw as linework (not as PDF text), with Tesseract OCR.

Labels such as "Proposed Loop at Level-1" are drawn as magenta pen strokes, so they cannot be searched or
copied from the PDF. For each sheet: draw only the short magenta strokes (lettering) into an image, group
nearby strokes into labels, turn each group horizontal (main axis of its pixels), and read it with
Tesseract in both orientations, keeping the more confident reading.

Needs tesseract with English data (Arch: pacman -S tesseract tesseract-data-eng).
Writes qgis/contract/out/ocr_labels.json: {page: [{text, conf, x, y, angle}]} in unrotated PDF points;
pages already in the file are skipped (delete it to redo). Run: .venv/bin/python qgis/contract/ocr.py [contract.pdf]
"""
import json, math, os, re, subprocess, sys, tempfile
import numpy as np, pymupdf
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PDF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '..', '..', 'docs', 'Ejipura to Silk Board Schedule A B C D F H I.pdf')
OUT = os.path.join(HERE, 'out', 'ocr_labels.json')
PAGES = range(24, 41)
K = 6                       # pixels per PDF point
LETTERING = (1.0, 0.0, 1.0)
MAX_STROKE = 12             # points; longer magenta lines are leaders and boundaries
GROUP = 4.5                 # points; strokes closer than this form one label
MIN_CONF = 60
WORD = re.compile(r'[A-Za-z]{3,}')

def ocr(img):
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        img.save(f.name)
        out = subprocess.run(['tesseract', f.name, '-', '--psm', '6', '-l', 'eng', 'tsv'], capture_output=True, text=True).stdout
    rows = [r.split('\t') for r in out.splitlines()[1:] if r.count('\t') >= 11 and r.split('\t')[11].strip()]
    if not rows: return '', 0.0
    lines, last = [], None
    for r in rows:                                   # keep tesseract's line breaks
        ln = (r[2], r[3], r[4])
        if ln != last: lines.append([]); last = ln
        lines[-1].append(r[11])
    return ' '.join(' '.join(l) for l in lines), float(np.mean([float(r[10]) for r in rows]))

def clean(t):
    t = t.replace('—', '-').replace('–', '-')
    t = re.sub(r'^[^A-Za-z0-9(]+', '', t); t = re.sub(r'[^A-Za-z0-9)]+$', '', t)
    return ' '.join(t.split())

def page_labels(page):
    W, H = int(page.mediabox.width * K), int(page.mediabox.height * K)
    img = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(img)
    for d in page.get_drawings():
        c = d.get('color')
        if not c or d.get('fill') or tuple(round(v, 2) for v in c) != LETTERING: continue
        for it in d['items']:
            if it[0] == 'l' and math.hypot(it[2].x - it[1].x, it[2].y - it[1].y) <= MAX_STROKE:
                dr.line([(it[1].x * K, it[1].y * K), (it[2].x * K, it[2].y * K)], fill=255, width=max(1, int(0.5 * K)))
    ink = np.array(img) > 0
    lab, _ = ndimage.label(ndimage.binary_dilation(ink, structure=np.ones((int(GROUP * K), int(GROUP * K)))))
    found = []
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        if max(h, w) < 6 * K or max(h, w) > 260 * K: continue
        mask = (lab[sl] == i) & ink[sl]
        ys, xs = np.nonzero(mask)
        if len(xs) < 50: continue
        ev, evec = np.linalg.eigh(np.cov(np.vstack([xs, ys])))
        ang = math.degrees(math.atan2(evec[1, 1], evec[0, 1]))
        crop = Image.fromarray(mask.astype(np.uint8) * 255)
        best = ('', 0.0, 0)
        for flip in (0, 180):
            rot = Image.eval(crop.rotate(ang + flip, expand=True, fillcolor=0), lambda v: 255 - v)
            rot = rot.resize((max(1, rot.width // 2), max(1, rot.height // 2)))
            pad = Image.new('L', (rot.width + 40, rot.height + 40), 255); pad.paste(rot, (20, 20))
            txt, conf = ocr(pad)
            if conf > best[1]: best = (txt, conf, flip)
        txt = clean(best[0])
        words = WORD.findall(txt)
        if best[1] < MIN_CONF or not words or sum(len(w) for w in words) < 0.6 * len(txt.replace(' ', '')):
            continue
        found.append({'text': txt, 'conf': round(best[1]), 'x': round((sl[1].start + sl[1].stop) / 2 / K, 1),
                      'y': round((sl[0].start + sl[0].stop) / 2 / K, 1), 'angle': round((ang + best[2]) % 360, 1)})
    return found

done = json.load(open(OUT)) if os.path.exists(OUT) else {}
doc = pymupdf.open(PDF)
for p in PAGES:
    if str(p) in done: continue
    done[str(p)] = page_labels(doc[p - 1])
    json.dump(done, open(OUT, 'w'), indent=1)
    print(f'page {p}: {len(done[str(p)])} labels', flush=True)
print(f'{sum(len(v) for v in done.values())} labels read on {len(done)} pages -> {OUT}')
