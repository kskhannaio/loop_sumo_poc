"""Draw a still picture of a simulation moment from SUMO's position output (no display needed).

Used to see where traffic is stuck when sumo-gui cannot be looked at. Lanes are drawn from the network, vehicles
from an FCD file (sumo --fcd-output) at one timestep: colour by type, a red outline when stopped.

  python snapshot.py NET FCD OUT.png LON LAT [half_width_m=120] [time]
"""
import math, sys, xml.etree.ElementTree as ET
from PIL import Image, ImageDraw
from common import read_net

net_f, fcd_f, out_f, lon, lat = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
half = float(sys.argv[6]) if len(sys.argv) > 6 else 120.0
want_t = sys.argv[7] if len(sys.argv) > 7 else None
net = read_net(net_f); cx, cy = net.convertLonLat2XY(lon, lat)
W = 1400; S = W / (2 * half)
px = lambda x, y: ((x - cx + half) * S, (cy + half - y) * S)
img = Image.new('RGB', (W, W), (245, 243, 238)); d = ImageDraw.Draw(img, 'RGBA')
for e in net.getEdges(withInternal=True):
    for l in e.getLanes():
        shp = l.getShape()
        if not any(abs(x - cx) < half + 30 and abs(y - cy) < half + 30 for x, y in shp): continue
        veh = l.allows('passenger'); ped = l.allows('pedestrian') and not veh
        col = (150, 150, 150, 255) if veh else (225, 215, 195, 255) if ped else (190, 190, 190, 255)
        if e.getFunction() == 'crossing': col = (255, 255, 255, 255)
        d.line([px(*p) for p in shp], fill=col, width=max(1, int(l.getWidth() * S) - 1))
        if veh and e.getFunction() != 'internal' and l.getLength() > 25:
            mx, my = shp[len(shp) // 2]; d.text(px(mx, my), f"{e.getID()}_{l.getIndex()}", fill=(60, 60, 60, 255))
COL = {'two_wheeler': (255, 140, 0), 'car': (40, 110, 220), 'auto': (30, 160, 70), 'bus': (220, 30, 30), 'person': (220, 0, 220)}
step = None
for ev, el in ET.iterparse(fcd_f, events=('start', 'end')):
    if ev == 'start' and el.tag == 'timestep': cur = el.get('time')
    if ev == 'end' and el.tag == 'timestep':
        if want_t is None or cur.startswith(want_t): step = el; break
        el.clear()
n = stopped = 0
for v in step:
    x, y = float(v.get('x')), float(v.get('y'))
    if abs(x - cx) > half or abs(y - cy) > half: continue
    X, Y = px(x, y)
    if v.tag == 'person': d.ellipse([X - 2, Y - 2, X + 2, Y + 2], fill=COL['person'] + (255,)); continue
    t = v.get('type'); col = COL.get(t, (130, 90, 50)); sp = float(v.get('speed')); a = math.radians(90 - float(v.get('angle')))
    L = {'two_wheeler': 2.0, 'car': 4.3, 'auto': 2.8, 'bus': 11.0}.get(t, 6.0); Wd = {'two_wheeler': 0.8, 'bus': 2.5}.get(t, 1.7)
    bx, by = x - math.cos(a) * L, y - math.sin(a) * L; nx, ny = -math.sin(a) * Wd / 2, math.cos(a) * Wd / 2
    poly = [px(x + nx, y + ny), px(x - nx, y - ny), px(bx - nx, by - ny), px(bx + nx, by + ny)]
    d.polygon(poly, fill=col + (255,), outline=(200, 0, 0, 255) if sp < 0.3 else (0, 0, 0, 255)); n += 1; stopped += sp < 0.3
d.text((10, 10), f"t={step.get('time')}  vehicles {n}, stopped {stopped} (red outline)   orange 2-wheeler, blue car, green auto, red bus, brown goods, magenta people", fill=(0, 0, 0, 255))
img.save(out_f); print(out_f, 'vehicles', n, 'stopped', stopped)
