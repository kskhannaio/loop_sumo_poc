"""Compare two scenarios over the same seeds (run scripts/seeds.py for each first).

  python scripts/compare.py baseline proposal_151126

Each seed is one random day; the two scenarios share seeds, so each seed gives a paired difference. A change is only
called a gain or a loss when all seeds agree on its direction. Writes out/metrics/compare_<a>_<b>.csv.
"""
import csv, os, statistics as st, sys
from common import P, JUNCTIONS

a, b = (sys.argv[1:3] + ['baseline', 'proposal_151126'])[:2] if len(sys.argv) < 3 else sys.argv[1:3]
seeds = sorted(set(os.listdir(P('out', 'seeds', a))) & set(os.listdir(P('out', 'seeds', b))), key=int)
seeds = [s for s in seeds if os.path.exists(P('out', 'seeds', a, s, 'metrics', 'summary.csv'))
         and os.path.exists(P('out', 'seeds', b, s, 'metrics', 'summary.csv'))]
if not seeds: sys.exit('no seeds run for both scenarios')

# (measure, higher is better?)
def values(scn, seed):
    rows = lambda n: list(csv.DictReader(open(P('out', 'seeds', scn, seed, 'metrics', n))))
    v = {}
    s = rows('summary.csv')[0]
    for j in JUNCTIONS: v[(f'Vehicles leaving junction {j} per hour', True)] = float(s[f'veh_through_{j}_per_h'])
    v[('Vehicles finishing their trip', True)] = float(s['vehicles_finished'])
    v[('Vehicles unable to enter the model', False)] = float(s['vehicles_not_inserted'])
    v[('Average vehicle delay, s', False)] = float(s['veh_delay_mean_s'])
    v[('Average bus delay, s', False)] = float(s['bus_delay_mean_s'])
    v[('Extra walk to cross, m (all roads)', False)] = float(s['ped_extra_walk_m_mean'])
    v[('Time lost walking, s (all roads)', False)] = float(s['ped_time_lost_mean_s'])
    v[('Teleports (stuck vehicles removed)', False)] = float(s['teleports'])
    if s.get('stepfree_extra_walk_m_mean'):
        v[('Extra walk to cross, people who cannot use stairs, m', False)] = float(s['stepfree_extra_walk_m_mean'])
        v[('Time to cross, people who cannot use stairs, s', False)] = float(s['stepfree_trip_time_mean_s'])
    for r in rows('junction_throughput.csv'):
        if r['junction'] == 'C':
            k = (f"  leaving C by {r['exit']}", True); v[k] = v.get(k, 0) + float(r['vehicles_per_h'])
    for r in rows('vehicles_by_side.csv'):
        if r['avg_speed_kmh']: v[(f"Speed {r['road']} {r['direction'].replace('>', ' to ')}, km/h", True)] = float(r['avg_speed_kmh'])
    for r in rows('people_by_side.csv'):
        v[(f"Extra walk to cross {r['road']}, m", False)] = float(r['extra_walk_m_mean'])
    for r in rows('queues.csv'):
        if r['signal'] == 'C': v[('Mean queue at C, worst lane, m', False)] = float(r['mean_queue_m_worst_lane'])
    return v

A = {s: values(a, s) for s in seeds}; B = {s: values(b, s) for s in seeds}
keys = [k for k in A[seeds[0]] if all(k in A[s] and k in B[s] for s in seeds)]
out = P('out', 'metrics', f'compare_{a}_{b}.csv')
with open(out, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['measure', 'higher_is_better', f'{a}_mean', f'{b}_mean', 'change_pct', 'paired_diff_min', 'paired_diff_max', 'verdict'] +
               [f'{a}_seed_{s}' for s in seeds] + [f'{b}_seed_{s}' for s in seeds])
    print(f"{a} vs {b}, seeds {', '.join(seeds)}\n")
    print(f"{'measure':52s} {a[:12]:>12s} {b[:12]:>12s} {'change':>8s}  verdict")
    for k in keys:
        name, up = k
        xa, xb = [A[s][k] for s in seeds], [B[s][k] for s in seeds]
        d = [y - x for x, y in zip(xa, xb)]
        ma, mb = st.mean(xa), st.mean(xb)
        pct = (mb - ma) / ma * 100 if ma else 0
        better = [x > 0 if up else x < 0 for x in d]; worse = [x < 0 if up else x > 0 for x in d]
        verdict = 'better in every run' if all(better) else 'worse in every run' if all(worse) else 'no clear change'
        w.writerow([name.strip(), up, round(ma, 1), round(mb, 1), round(pct, 1), round(min(d), 1), round(max(d), 1), verdict] + xa + xb)
        print(f"{name:52s} {ma:12.1f} {mb:12.1f} {pct:+7.1f}%  {verdict}")
print('\nwrote', out)
