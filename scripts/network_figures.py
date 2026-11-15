"""Before/after pictures of the street network: today vs the trial crossings.

Draws lanes, footpaths, junctions and crossings to scale from the SUMO networks.
Writes report/before_after_loop.png (whole loop) and report/before_after_closeups.png
(one new crossing per road). Run by report.py, or on its own after the networks exist.
"""
import csv, math, os, warnings
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from common import P, JUNCTIONS, SIDE_NAME, sumolib

warnings.filterwarnings('ignore')
BG, ROAD, JUNC, FOOT, ZEBRA, NEW = '#f4f2ec', '#8e9196', '#9a9da2', '#e2d6bd', '#1d1d1b', '#7048e8'
CLOSEUPS = [('BC', 340), ('CA', 210), ('AB', 410)]       # one new crossing per road
HALF = (75, 52)                                          # close-up half-size in metres (x, y)


def ribbon(shape, width):
    """Polygon of a centreline buffered to `width` metres (square ends)."""
    if len(shape) < 2: return None
    left, right = [], []
    for i, (x, y) in enumerate(shape):
        a, b = shape[max(i - 1, 0)], shape[min(i + 1, len(shape) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L * width / 2, dx / L * width / 2
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def near(shape, box, pad=40):
    x0, y0, x1, y1 = box
    return any(x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad for x, y in shape)


def draw(ax, net, box, new_nodes, closeup):
    x0, y0, x1, y1 = box
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.axis('off')
    ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color=BG, zorder=0))
    pts_per_m = ax.get_window_extent().width / (x1 - x0) * 72 / ax.figure.dpi
    for n in net.getNodes():                                          # junction areas
        s = n.getShape()
        if len(s) > 2 and near(s, box): ax.add_patch(Polygon(s, color=JUNC, lw=0, zorder=1))
    crossings = []
    for e in net.getEdges(withInternal=True):
        f = e.getFunction()
        if f == 'internal': continue
        for lane in e.getLanes():
            s = lane.getShape()
            if not near(s, box): continue
            if f == 'walkingarea':
                if len(s) > 2: ax.add_patch(Polygon(s, color=FOOT, lw=0, zorder=2))
            elif f == 'crossing':
                crossings.append((e, lane))
            else:
                walk = lane.allows('pedestrian') and not lane.allows('passenger')
                if not walk and not lane.allows('passenger') and not lane.allows('bus'): continue
                poly = ribbon(s, lane.getWidth() - (0 if walk else 0.25))
                if poly: ax.add_patch(Polygon(poly, color=FOOT if walk else ROAD, lw=0, zorder=2 if walk else 1.5))
    for e, lane in crossings:                                         # zebra stripes: white base + dashed bars
        s = lane.getShape(); is_new = e.getID()[1:].split('_c')[0] in new_nodes
        poly = ribbon(s, lane.getWidth())
        ax.add_patch(Polygon(poly, color='white', lw=0, zorder=3))
        if closeup:
            xs, ys = zip(*s)
            ax.plot(xs, ys, color=NEW if is_new else ZEBRA, lw=lane.getWidth() * 0.8 * pts_per_m, solid_capstyle='butt',
                    dashes=(0.5 / (0.8 * 0.6), 0.5 / (0.8 * 0.6)), zorder=4)
        else:
            cx, cy = sum(p[0] for p in s) / len(s), sum(p[1] for p in s) / len(s)
            ax.plot(cx, cy, 's', ms=8 if is_new else 3.2, color=NEW if is_new else '#6c6f73',
                    mec='white', mew=0.8 if is_new else 0.3, zorder=5 if is_new else 4)
    return pts_per_m


def main():
    os.makedirs(P('report'), exist_ok=True)
    base = sumolib.net.readNet(P('net', 'baseline.net.xml'), withInternal=True)
    trial = sumolib.net.readNet(P('net', 'trial_crossings.net.xml'), withInternal=True)
    sites = list(csv.DictReader(open(P('out', 'checks', 'trial_crossings.csv'))))
    new_nodes = {r['tls_id'] for r in sites}
    titles = ('Today', 'With the trial crossings')

    # whole loop
    jxy = [base.convertLonLat2XY(*ll) for ll in JUNCTIONS.values()]
    pad = 110
    box = (min(x for x, _ in jxy) - pad, min(y for _, y in jxy) - pad, max(x for x, _ in jxy) + pad, max(y for _, y in jxy) + pad)
    fig, axs = plt.subplots(1, 2, figsize=(13, 6.6), facecolor='white')
    for ax, net, t in zip(axs, (base, trial), titles):
        draw(ax, net, box, new_nodes if net is trial else set(), False)
        for j, ll in JUNCTIONS.items():
            x, y = net.convertLonLat2XY(*ll)
            ax.plot(x, y, 'o', ms=17, color='#1d1d1b', zorder=6, mec='white', mew=1.2)
            ax.text(x, y, j, color='white', ha='center', va='center', fontsize=10, weight='bold', zorder=7)
        ax.set_title(t, fontsize=14, weight='bold', loc='left')
    for r in sites:
        x, y = trial.convertLonLat2XY(float(r['lon']), float(r['lat']))
        axs[1].annotate(f"{r['dist_from_first_junction_m']} m", (x, y), xytext=(7, 6), textcoords='offset points',
                        fontsize=8, color=NEW, weight='bold', zorder=8)
    fig.text(0.01, 0.015, 'Squares mark pedestrian crossings: grey = existing (junctions and side streets), purple = new signalised '
             'crossing,\nlabelled with its distance from the road\'s first junction. Roads in grey, footpaths in beige.',
             fontsize=9, color='#444')
    fig.tight_layout(rect=(0, 0.06, 1, 0.97))
    fig.savefig(P('report', 'before_after_loop.png'), dpi=130); plt.close(fig)

    # close-ups, one per road
    fig, axs = plt.subplots(len(CLOSEUPS), 2, figsize=(11, 3.75 * len(CLOSEUPS)), facecolor='white')
    for row, (side, dist) in zip(axs, CLOSEUPS):
        r = next(r for r in sites if r['side'] == side and int(r['dist_from_first_junction_m']) == dist)
        cx, cy = trial.convertLonLat2XY(float(r['lon']), float(r['lat']))
        box = (cx - HALF[0], cy - HALF[1], cx + HALF[0], cy + HALF[1])
        for ax, net, t in zip(row, (base, trial), titles):
            draw(ax, net, box, new_nodes if net is trial else set(), True)
            ax.set_title(f'{t}: {SIDE_NAME[side]}, {dist} m from {side[0]}', fontsize=11, loc='left')
            ax.plot([box[2] - 30, box[2] - 10], [box[1] + 6] * 2, color='#1d1d1b', lw=2, zorder=9)
            ax.text(box[2] - 20, box[1] + 9, '20 m', ha='center', fontsize=8, zorder=9)
        row[1].annotate('new signalised crossing', (cx, cy), xytext=(cx + 22, cy + 30), fontsize=9, color=NEW, weight='bold',
                        arrowprops=dict(arrowstyle='->', color=NEW, lw=1.4), zorder=10)
    fig.text(0.01, 0.006, 'Drawn to scale from the simulation network. Grey = vehicle lanes, beige = footpaths,\n'
             'black stripes = existing crossings, purple stripes = new crossing (spans both directions of traffic).',
             fontsize=9, color='#444')
    fig.tight_layout(rect=(0, 0.025, 1, 0.99))
    fig.savefig(P('report', 'before_after_closeups.png'), dpi=130); plt.close(fig)
    print('wrote report/before_after_loop.png, report/before_after_closeups.png')


if __name__ == '__main__':
    main()
