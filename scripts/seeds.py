"""Run one scenario with several random seeds and report how much the results move.

  python scripts/seeds.py                    baseline, seeds 1 2 3 4 and the configured one
  python scripts/seeds.py baseline 7 8 9     chosen scenario and seeds
  python scripts/seeds.py --no-sim           recompute the figures from runs already on disk

Each seed changes SUMO's randomness only (driver imperfection, vehicle type drawn for each trip, lane choice);
the trips themselves are the same. Runs go side by side into out/seeds/<scenario>/<seed>/ and leave out/<scenario> untouched.
Writes out/metrics/seed_spread_<scenario>.csv.
"""
import csv, os, statistics as st, subprocess, sys
from common import P, cfg

args = [a for a in sys.argv[1:] if a != '--no-sim']; no_sim = '--no-sim' in sys.argv
scn = args[0] if args else 'baseline'
seeds = [int(x) for x in args[1:]] or [1, 2, 3, 4, cfg()['time']['seed']]
here = os.path.dirname(os.path.abspath(__file__))

procs = []
for s in seeds:
    out = P('out', 'seeds', scn, str(s)); os.makedirs(out, exist_ok=True)
    env = dict(os.environ, SIM_OUT=out, SUMO_SEED=str(s))
    cmd = (f'"{sys.executable}" metrics.py' if no_sim else f'"{sys.executable}" run_sim.py {scn} && "{sys.executable}" metrics.py')
    procs.append((s, subprocess.Popen(cmd, shell=True, cwd=here, env=env, stdout=open(os.path.join(out, 'run.log'), 'w'),
                                      stderr=subprocess.STDOUT)))
for s, p in procs:
    if p.wait(): sys.exit(f'seed {s} failed - see out/seeds/{scn}/{s}/run.log')

def rows(seed, name):
    return list(csv.DictReader(open(P('out', 'seeds', scn, str(seed), 'metrics', name))))

vals = {}                                             # measure -> [value per seed]
def add(key, v):
    try: vals.setdefault(key, []).append(float(v))
    except (TypeError, ValueError): pass
for s in seeds:
    for r in rows(s, 'summary.csv'):
        for k in ('vehicles_finished', 'vehicles_not_inserted', 'veh_delay_mean_s', 'bus_delay_mean_s', 'teleports',
                  'ped_time_lost_mean_s', 'ped_extra_walk_m_mean'): add(k, r[k])
    for r in rows(s, 'vehicles_by_side.csv'):
        add(f"speed_kmh {r['road']} {r['direction']}", r['avg_speed_kmh'])
        add(f"veh_per_h {r['road']} {r['direction']}", r['vehicles_per_h'])
    for r in rows(s, 'people_by_side.csv'):
        add(f"extra_walk_m {r['road']}", r['extra_walk_m_mean'])
        add(f"ped_time_lost_s {r['road']}", r['time_lost_mean_s'])
    for r in rows(s, 'crossings_use.csv'): add(f"people_per_h crossing {r['crossing']}", r['people_per_h'])

out = P('out', 'metrics', f'seed_spread_{scn}.csv')
with open(out, 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['measure', 'mean', 'min', 'max', 'spread_pct_of_mean'] + [f'seed_{s}' for s in seeds])
    for k, v in vals.items():
        if len(v) != len(seeds): continue
        m = st.mean(v); sp = (max(v) - min(v)) / m * 100 if m else 0
        w.writerow([k, round(m, 1), min(v), max(v), round(sp, 1)] + v)
        print(f'{k:52s} mean {m:9.1f}   {min(v):9.1f} to {max(v):9.1f}   ({sp:.0f}% of mean)')
print('wrote', out)
