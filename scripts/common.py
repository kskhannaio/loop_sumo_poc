"""Shared paths, config and geometry helpers for the Madiwala loop SUMO model."""
import json, math, os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
import sumo  # eclipse-sumo wheel
SUMO_HOME = sumo.SUMO_HOME
os.environ['SUMO_HOME'] = SUMO_HOME
sys.path.insert(0, os.path.join(SUMO_HOME, 'tools'))
import sumolib  # noqa: E402

BIN = lambda name: os.path.join(SUMO_HOME, 'bin', name)
P = lambda *a: os.path.join(ROOT, *a)
# run outputs; scripts/seeds.py points SIM_OUT at out/seeds/<seed> to run several seeds side by side
O = lambda *a: P(os.environ.get('SIM_OUT', 'out'), *a)
SCENARIOS = ['baseline', 'trial_crossings', 'flyover_opened']
# drawn proposals (config "proposals", built by make_proposal.py) run as further scenarios
SCENARIOS += [k for k in json.load(open(os.path.join(ROOT, 'config', 'assumptions.json'))).get('proposals', {}) if not k.startswith('_')]
SIDES = ['AB', 'BC', 'CA']
SIDE_NAME = {'AB': '100 Feet Road', 'BC': 'Hosur Road', 'CA': 'Sarjapura Road'}
JUNCTIONS = {'A': (77.620965, 12.927461), 'B': (77.618093, 12.924584), 'C': (77.614971, 12.929885)}


def cfg():
    return json.load(open(P('config', 'assumptions.json')))


def behaviour_opts():
    """SUMO options for driver behaviour shared by every run (config "vehicles")."""
    v = cfg().get('vehicles', {})
    if not v.get('rerouting_probability'): return []
    # the device itself is switched on per vehicle type in make_demand.py (not for buses: rerouting a bus with stops can
    # plan an impossible U-turn and crash SUMO); these options only set how it behaves
    return ['--device.rerouting.period', str(v['rerouting_period_s']), '--device.rerouting.pre-period', '1',
            '--device.rerouting.adaptation-steps', str(v.get('rerouting_adaptation_steps', 18)), '--device.rerouting.adaptation-interval', '10']


def hhmm(t):
    h, m = t.split(':'); return int(h) * 3600 + int(m) * 60


def run(cmd, log=None, check=True):
    """Run a command; stream a short tail of output; raise on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or '') + (r.stderr or '')
    lines = [l for l in out.splitlines() if 'proj.db' not in l]
    if log:
        with open(log, 'w') as f: f.write('\n'.join(lines))
    if check and r.returncode != 0:
        print('\n'.join(lines[-40:])); raise SystemExit(f'failed: {" ".join(cmd[:3])} ...')
    return lines


# ---- study geometry (copied from the website repo into inputs/) -------------------------------
def load_geo(name):
    return json.load(open(P('inputs', name)))['features']


R_EARTH = 6371008.8
KX = math.radians(1) * R_EARTH * math.cos(math.radians(12.927))
KY = math.radians(1) * R_EARTH
LL2M = lambda c: (c[0] * KX, c[1] * KY)
M2LL = lambda p: (p[0] / KX, p[1] / KY)


class Centreline:
    """A loop side's centreline (lon/lat) with distance-along helpers."""
    def __init__(self, coords):
        self.pts = [LL2M(c) for c in coords]
        self.ch = [0.0]
        for a, b in zip(self.pts, self.pts[1:]): self.ch.append(self.ch[-1] + math.dist(a, b))
        self.length = self.ch[-1]

    def at(self, d):
        d = max(0.0, min(self.length, d))
        for i in range(len(self.ch) - 1):
            if self.ch[i] <= d <= self.ch[i + 1]:
                t = (d - self.ch[i]) / ((self.ch[i + 1] - self.ch[i]) or 1)
                a, b = self.pts[i], self.pts[i + 1]
                L = math.dist(a, b) or 1
                return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])), ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        return self.pts[-1], (1.0, 0.0)


def centrelines():
    out = {}
    for f in load_geo('crossings.geojson'):
        p = f['properties']
        if p['kind'] == 'centreline': out[p['side']] = Centreline(f['geometry']['coordinates'])
    return out


def carriageways():
    """{(side, from, to): [lon/lat coords]} for the six one-way carriageways of the loop."""
    return {(f['properties']['side'], f['properties']['from'], f['properties']['to']): f['geometry']['coordinates']
            for f in load_geo('stretch.geojson') if f['properties']['kind'] == 'carriageway'}


def read_net(path):
    import warnings; warnings.filterwarnings('ignore')
    return sumolib.net.readNet(path, withPrograms=True)
